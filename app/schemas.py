from pydantic import BaseModel, Field


class CreateCategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class AddWordsRequest(BaseModel):
    words: list[str]


class CreateGameRequest(BaseModel):
    host_name: str = Field(min_length=1, max_length=32)
    num_auctions: int = Field(default=5, ge=1, le=10)
    starting_money: int = Field(default=100, ge=1, le=100000)
    refill_amount: int = Field(default=20, ge=0, le=100000)
    refill_interval: int = Field(default=5, ge=1, le=50)
    round_pattern: list[str] = Field(default_factory=lambda: ["bid", "bid", "word"])
    pattern_repeat: int = Field(default=3, ge=1, le=20)
    category_ids: list[int] = Field(default_factory=list)


class JoinGameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)


class BidRequest(BaseModel):
    bids: dict[str, int]


class PickLetterRequest(BaseModel):
    auction_index: int
    letter: str = Field(min_length=1, max_length=2)


class WordSubmitRequest(BaseModel):
    # min_length=0: a jatekosnak lehetosege kell legyen ures szot ("nincs szavam")
    # bekuldeni, ha a birtokolt betuibol nem tud semmit kirakni ebben a korben.
    word: str = Field(min_length=0, max_length=64)
