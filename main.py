from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, UUID4
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime, timedelta
import jwt
import yfinance as yf
import sqlite3
import uuid
from typing import List, Optional, Dict, Any
import bcrypt
from contextlib import contextmanager

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./finance_portfolio.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# JWT Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# FastAPI setup
app = FastAPI(title="Finance Portfolio API", version="1.0.0")
security = HTTPBearer()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    portfolios = relationship("Portfolio", back_populates="user")
    watchlists = relationship("Watchlist", back_populates="user")

class Portfolio(Base):
    __tablename__ = "portfolios"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, default="Default Portfolio")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="portfolios")
    positions = relationship("Position", back_populates="portfolio", cascade="all, delete-orphan")

class Position(Base):
    __tablename__ = "positions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id = Column(String, ForeignKey("portfolios.id"), nullable=False)
    ticker = Column(String, nullable=False)
    shares = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    portfolio = relationship("Portfolio", back_populates="positions")

class Watchlist(Base):
    __tablename__ = "watchlists"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tickers = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="watchlists")

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic Models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class StockInfo(BaseModel):
    ticker: str
    name: str
    price: float
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    currency: Optional[str] = None

class PositionAdd(BaseModel):
    ticker: str
    shares: int

class PositionResponse(BaseModel):
    id: str
    ticker: str
    shares: int
    created_at: datetime

class PortfolioResponse(BaseModel):
    id: str
    name: str
    positions: List[PositionResponse]
    created_at: datetime

class TickerAdd(BaseModel):
    ticker: str

class WatchlistResponse(BaseModel):
    id: str
    tickers: List[str]
    created_at: datetime

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# # Stock data functions
# def get_stock_info(ticker: str) -> Dict[str, Any]:
#     try:
#         stock = yf.Ticker(ticker.upper())
#         info = stock.info
        
#         if not info or 'regularMarketPrice' not in info:
#             # Try to get current price if info is incomplete
#             hist = stock.history(period="1d")
#             if hist.empty:
#                 raise ValueError("Stock not found")
#             current_price = hist['Close'].iloc[-1]
#         else:
#             current_price = info.get('regularMarketPrice', 0)
        
#         return {
#             "ticker": ticker.upper(),
#             "name": info.get('longName', info.get('shortName', ticker.upper())),
#             "price": float(current_price),
#             "sector": info.get('sector'),
#             "market_cap": info.get('marketCap'),
#             "currency": info.get('currency', 'USD')
#         }
#     except Exception as e:
#         raise HTTPException(status_code=404, detail=f"Stock {ticker} not found or data unavailable")


# Stock data functions
def get_stock_info(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker.upper())
        print(f"stock: {stock.info}")
        # Try multiple methods to get stock data
        current_price = None

        info = {}
        
        data = stock.history(period="1d")
        print(f"{ticker} data:", data)
        
        try:
            # Method 1: Try to get info first
            info = stock.info
            print(f"info: {info}")
            if info and len(info) > 1:  # Check if info has meaningful data
                current_price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
        except:
            pass
        
        # Method 2: If info failed or price not found, try history
        if current_price is None:
            try:
                hist = stock.history(period="5d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            except:
                pass
        
        # Method 3: Try fast_info as fallback
        if current_price is None:
            try:
                fast_info = stock.fast_info
                current_price = fast_info.get('lastPrice') or fast_info.get('regularMarketPrice')
            except:
                pass
        
        # If we still don't have a price, the stock likely doesn't exist
        if current_price is None or current_price <= 0:
            raise ValueError("Stock not found or invalid")
        
        # Get name with fallbacks
        name = (info.get('longName') or 
                info.get('shortName') or 
                ticker.upper())
        
        return {
            "ticker": ticker.upper(),
            "name": name,
            "price": float(current_price),
            "sector": info.get('sector', "N/A"),
            "market_cap": info.get('marketCap'),
            "currency": info.get('currency', 'USD')
        }
        
    except Exception as e:
        print(f"Error fetching stock data for {ticker}: {str(e)}")  # Debug logging
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found or data unavailable")



# Auth endpoints
@app.post("/auth/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    if db.query(User).filter((User.username == user_data.username) | (User.email == user_data.email)).first():
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Create user
    hashed_pw = hash_password(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_pw
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create default portfolio and watchlist
    portfolio = Portfolio(user_id=db_user.id, name="Default Portfolio")
    watchlist = Watchlist(user_id=db_user.id, tickers=[])
    db.add(portfolio)
    db.add(watchlist)
    db.commit()
    
    # Create access token
    access_token = create_access_token(data={"sub": db_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Stock research endpoints
@app.get("/research/{ticker}", response_model=StockInfo)
async def get_stock_research(ticker: str, current_user: User = Depends(get_current_user)):
    return get_stock_info(ticker)

# Portfolio endpoints
@app.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio

@app.post("/portfolio/add")
async def add_position(
    position_data: PositionAdd, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # Validate ticker
    get_stock_info(position_data.ticker)
    
    # Validate shares
    if position_data.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be positive")
    
    # Get user's portfolio
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    # Check if position already exists
    existing_position = db.query(Position).filter(
        Position.portfolio_id == portfolio.id,
        Position.ticker == position_data.ticker.upper()
    ).first()
    
    if existing_position:
        existing_position.shares += position_data.shares
    else:
        new_position = Position(
            portfolio_id=portfolio.id,
            ticker=position_data.ticker.upper(),
            shares=position_data.shares
        )
        db.add(new_position)
    
    db.commit()
    return {"message": f"Added {position_data.shares} shares of {position_data.ticker.upper()}"}

@app.post("/portfolio/remove")
async def remove_position(
    position_data: PositionAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get user's portfolio
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == current_user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    # Find existing position
    position = db.query(Position).filter(
        Position.portfolio_id == portfolio.id,
        Position.ticker == position_data.ticker.upper()
    ).first()
    
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    if position_data.shares >= position.shares:
        # Remove entire position
        db.delete(position)
        message = f"Removed all shares of {position_data.ticker.upper()}"
    else:
        # Reduce shares
        position.shares -= position_data.shares
        message = f"Reduced {position_data.ticker.upper()} by {position_data.shares} shares"
    
    db.commit()
    return {"message": message}

# Watchlist endpoints
@app.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).first()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return watchlist

@app.post("/watchlist/add")
async def add_to_watchlist(
    ticker_data: TickerAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate ticker
    get_stock_info(ticker_data.ticker)
    
    # Get user's watchlist
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).first()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    ticker_upper = ticker_data.ticker.upper()
    if ticker_upper not in watchlist.tickers:
        watchlist.tickers.append(ticker_upper)
        db.commit()
        return {"message": f"Added {ticker_upper} to watchlist"}
    else:
        return {"message": f"{ticker_upper} already in watchlist"}

@app.post("/watchlist/remove")
async def remove_from_watchlist(
    ticker_data: TickerAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get user's watchlist
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).first()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    ticker_upper = ticker_data.ticker.upper()
    if ticker_upper in watchlist.tickers:
        watchlist.tickers.remove(ticker_upper)
        db.commit()
        return {"message": f"Removed {ticker_upper} from watchlist"}
    else:
        raise HTTPException(status_code=404, detail="Ticker not in watchlist")

# Health check
@app.get("/")
async def root():
    return {"message": "Finance Portfolio API is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
