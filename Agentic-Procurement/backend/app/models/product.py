from pydantic import BaseModel

class Product(BaseModel):
    sku: str
    name: str
    category: str
    price: float
    inventory: int
    lead_time: int  # in days
    moq: int        # minimum order quantity
    description: str
