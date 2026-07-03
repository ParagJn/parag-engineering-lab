import os
from typing import List, Dict, Optional
from app.repositories.base_repo import BaseRepository
from app.models.product import Product

DEFAULT_PRODUCTS = [
    {"sku": "SODA-001", "name": "FizzCola Classic", "category": "Soda", "price": 1.50, "inventory": 2000, "lead_time": 2, "moq": 100, "description": "Classic sparkling cola beverage."},
    {"sku": "SODA-002", "name": "DietFizz Lemon-Lime", "category": "Soda", "price": 1.60, "inventory": 1800, "lead_time": 2, "moq": 100, "description": "Zero calorie lemon-lime soda."},
    {"sku": "SODA-003", "name": "WildCherry Pop", "category": "Soda", "price": 1.70, "inventory": 1500, "lead_time": 2, "moq": 100, "description": "Sweet wild cherry flavored soda."},
    {"sku": "CHIP-001", "name": "CrunchySalt Potato Chips", "category": "Chips", "price": 2.20, "inventory": 1000, "lead_time": 3, "moq": 50, "description": "Crispy salted potato chips."},
    {"sku": "CHIP-002", "name": "SpicyBarbecue Crisps", "category": "Chips", "price": 2.40, "inventory": 900, "lead_time": 3, "moq": 50, "description": "Smokey and spicy barbecue chips."},
    {"sku": "CHIP-003", "name": "CheddarSourCream Crisps", "category": "Chips", "price": 2.50, "inventory": 850, "lead_time": 3, "moq": 50, "description": "Creamy cheddar and sour cream potato chips."},
    {"sku": "SNAK-001", "name": "ProteinPower Bar", "category": "Snacks", "price": 2.80, "inventory": 1200, "lead_time": 4, "moq": 80, "description": "High protein chocolate peanut butter bar."},
    {"sku": "SNAK-002", "name": "VeggieStraws Original", "category": "Snacks", "price": 3.00, "inventory": 800, "lead_time": 4, "moq": 60, "description": "Crispy vegetable straws lightly salted."},
    {"sku": "SNAK-003", "name": "RoastedAlmonds Salted", "category": "Snacks", "price": 4.80, "inventory": 600, "lead_time": 4, "moq": 50, "description": "Premium roasted almonds with sea salt."},
    {"sku": "ENER-001", "name": "BoltEnergy Original", "category": "Energy Drinks", "price": 2.90, "inventory": 1500, "lead_time": 3, "moq": 120, "description": "High energy drink with taurine and caffeine."},
    {"sku": "ENER-002", "name": "BoltEnergy BlueRaspberry", "category": "Energy Drinks", "price": 3.10, "inventory": 1300, "lead_time": 3, "moq": 120, "description": "Sugar-free blue raspberry energy drink."},
    {"sku": "ENER-003", "name": "BoltEnergy Citrus Blend", "category": "Energy Drinks", "price": 3.00, "inventory": 1400, "lead_time": 3, "moq": 120, "description": "Tangy citrus blend energy drink."},
    {"sku": "COOK-001", "name": "ChocoDelight Cookies", "category": "Cookies", "price": 3.50, "inventory": 700, "lead_time": 5, "moq": 50, "description": "Double chocolate chip cookies."},
    {"sku": "COOK-002", "name": "OatsNHoney Biscuits", "category": "Cookies", "price": 2.80, "inventory": 900, "lead_time": 5, "moq": 50, "description": "Wholesome oats and sweet honey cookies."},
    {"sku": "COOK-003", "name": "VanillaSwirl Sandwiches", "category": "Cookies", "price": 3.20, "inventory": 650, "lead_time": 5, "moq": 50, "description": "Creamy vanilla filling sandwich cookies."},
    {"sku": "CRAC-001", "name": "SeaSalt Crackers", "category": "Crackers", "price": 1.80, "inventory": 1600, "lead_time": 3, "moq": 100, "description": "Thin crispy sea salt crackers."},
    {"sku": "CRAC-002", "name": "CheddarCheese Thins", "category": "Crackers", "price": 2.00, "inventory": 1400, "lead_time": 3, "moq": 100, "description": "Real cheddar cheese baked crackers."},
    {"sku": "JUIC-001", "name": "PureOrange Juice", "category": "Juice", "price": 4.20, "inventory": 500, "lead_time": 2, "moq": 40, "description": "100% freshly squeezed orange juice."},
    {"sku": "JUIC-002", "name": "RubyGrapefruit Juice", "category": "Juice", "price": 4.50, "inventory": 450, "lead_time": 2, "moq": 40, "description": "Tart and refreshing grapefruit juice."},
    {"sku": "JUIC-003", "name": "AppleOrchard Cider", "category": "Juice", "price": 3.90, "inventory": 550, "lead_time": 2, "moq": 40, "description": "Crisp and sweet apple cider juice."}
]

class ProductsRepository:
    def __init__(self, data_dir: str):
        self.products_file = os.path.join(data_dir, "products.json")
        self.inventory_file = os.path.join(data_dir, "inventory.json")
        
        # Prepare static product details
        clean_products = []
        for dp in DEFAULT_PRODUCTS:
            prod_copy = dp.copy()
            prod_copy.pop("inventory")
            clean_products.append(prod_copy)
            
        self.products_repo = BaseRepository(self.products_file, default_data=clean_products)
        
        # Prepare initial inventory mapping
        default_inventory = {p["sku"]: p["inventory"] for p in DEFAULT_PRODUCTS}
        self.inventory_repo = BaseRepository(self.inventory_file, default_data=default_inventory)

    def get_all(self) -> List[Product]:
        products_data = self.products_repo.load()
        inventory_data = self.inventory_repo.load()
        
        res = []
        for p in products_data:
            sku = p["sku"]
            qty = inventory_data.get(sku, 0)
            res.append(Product(
                sku=sku,
                name=p["name"],
                category=p["category"],
                price=p["price"],
                inventory=qty,
                lead_time=p["lead_time"],
                moq=p["moq"],
                description=p["description"]
            ))
        return res

    def get_by_sku(self, sku: str) -> Optional[Product]:
        products = self.get_all()
        for p in products:
            if p.sku == sku:
                return p
        return None

    def update_inventory(self, sku: str, quantity: int) -> bool:
        inventory_data = self.inventory_repo.load()
        if sku in inventory_data:
            inventory_data[sku] = max(0, quantity)
            self.inventory_repo.save(inventory_data)
            return True
        return False

    def rebuild_db(self):
        clean_products = []
        default_inventory = {}
        for dp in DEFAULT_PRODUCTS:
            prod_copy = dp.copy()
            inventory_qty = prod_copy.pop("inventory")
            clean_products.append(prod_copy)
            default_inventory[dp["sku"]] = inventory_qty
            
        self.products_repo.save(clean_products)
        self.inventory_repo.save(default_inventory)

    def reset_inventory(self):
        default_inventory = {p["sku"]: p["inventory"] for p in DEFAULT_PRODUCTS}
        self.inventory_repo.save(default_inventory)
