from datetime import date, datetime
from pydantic import BaseModel


# --- Stock ---

class StockInfo(BaseModel):
    symbol: str
    market: str  # 'JP' or 'US'
    name: str | None = None
    sector: str | None = None
    currency: str = "JPY"


class OHLCV(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockDetail(BaseModel):
    info: StockInfo
    latest_price: OHLCV | None = None


class StockListResponse(BaseModel):
    stocks: list[StockInfo]
    total: int


class PriceListResponse(BaseModel):
    symbol: str
    market: str
    prices: list[OHLCV]


# --- Sync ---

class SyncRequest(BaseModel):
    symbol: str
    market: str  # 'JP' or 'US'
    from_date: date | None = None
    to_date: date | None = None


class SyncResponse(BaseModel):
    symbol: str
    market: str
    fetched_count: int
    message: str


# --- Indicators ---

class IndicatorValue(BaseModel):
    date: date
    value: float | None = None


class BollingerBandValue(BaseModel):
    date: date
    upper: float | None = None
    middle: float | None = None
    lower: float | None = None


class MACDValue(BaseModel):
    date: date
    macd: float | None = None
    signal: float | None = None
    histogram: float | None = None


class IndicatorsResponse(BaseModel):
    symbol: str
    market: str
    ma: dict[str, list[IndicatorValue]] | None = None      # key: period ("5", "25", "75")
    rsi: list[IndicatorValue] | None = None
    macd: list[MACDValue] | None = None
    bollinger: list[BollingerBandValue] | None = None


# --- Trade ---

class TradeRequest(BaseModel):
    symbol: str
    market: str
    side: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    note: str | None = None


class TradeRecord(BaseModel):
    id: int
    symbol: str
    market: str
    side: str
    quantity: int
    price: float
    executed_at: datetime
    note: str | None = None


class TradeStats(BaseModel):
    total_trades: int
    total_realized_pnl: float
    win_count: int
    lose_count: int
    win_rate: float
    avg_gain: float
    avg_loss: float


# --- Account / Portfolio ---

class AccountInfo(BaseModel):
    cash_balance: float
    portfolio_value: float
    total_value: float


class Holding(BaseModel):
    symbol: str
    market: str
    name: str | None = None
    quantity: int
    avg_cost: float
    current_price: float | None = None
    unrealized_pnl: float | None = None


class PortfolioResponse(BaseModel):
    holdings: list[Holding]
    total_unrealized_pnl: float


class AllocationItem(BaseModel):
    label: str
    value: float
    percentage: float


class AllocationResponse(BaseModel):
    by_market: list[AllocationItem]
    by_sector: list[AllocationItem]


# --- Screening ---

class ScreeningResult(BaseModel):
    symbol: str
    market: str
    name: str | None = None
    sector: str | None = None
    close: float | None = None
    volume: int | None = None
    avg_volume: float | None = None
    volatility: float | None = None
    change_pct: float | None = None
