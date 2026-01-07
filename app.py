import asyncio
import tornado.web
import tornado.ioloop
import tornado.escape
from bson import ObjectId
from pymongo import AsyncMongoClient

# Configurazione Database
client = AsyncMongoClient("mongodb://localhost:27017")
db = client["catalogueDB"]
products_collection = db["products"]

# --- HANDLER PER IL FRONTEND (HTML) ---

class ProductListHandler(tornado.web.RequestHandler):
    async def get(self):
        # Gestione del filtro categoria
        category_filter = self.get_argument("category", "Tutte")
        
        query = {}
        if category_filter != "Tutte":
            query["category"] = category_filter

        products = []
        cursor = products_collection.find(query)
        async for doc in cursor:
            products.append({
                "id": str(doc["_id"]),
                "name": doc["name"],
                "price": doc["price"],
                "category": doc["category"],
                "available": doc["available"]
            })
        
        # Renderizza la pagina passando i prodotti e il filtro corrente
        self.render("products.html", products=products, current_category=category_filter)

class NewProductHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("new_product.html")

    async def post(self):
        name = self.get_body_argument("name")
        price = float(self.get_body_argument("price"))
        category = self.get_body_argument("category")
        # Checkbox: se presente vale True, altrimenti False
        available = self.get_body_argument("available", None) is not None

        await products_collection.insert_one({
            "name": name,
            "price": price,
            "category": category,
            "available": available
        })
        self.redirect("/products")

class DeleteProductHandler(tornado.web.RequestHandler):
    async def post(self, product_id):
        await products_collection.delete_one({"_id": ObjectId(product_id)})
        self.redirect("/products")

class ToggleProductHandler(tornado.web.RequestHandler):
    async def post(self, product_id):
        doc = await products_collection.find_one({"_id": ObjectId(product_id)})
        if doc:
            await products_collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {"available": not doc["available"]}}
            )
        self.redirect("/products")

# --- HANDLER PER LE API (JSON) ---

class ProductsAPIHandler(tornado.web.RequestHandler):
    async def get(self):
        products = []
        cursor = products_collection.find({})
        async for doc in cursor:
            products.append({
                "id": str(doc["_id"]),
                "name": doc["name"],
                "price": doc["price"],
                "category": doc["category"],
                "available": doc["available"]
            })
        self.write({"products": products})

    async def post(self):
        # Decodifica il JSON ricevuto nel body
        data = tornado.escape.json_decode(self.request.body)
        
        new_product = {
            "name": data["name"],
            "price": float(data["price"]),
            "category": data["category"],
            "available": data.get("available", False) # Default false se non specificato
        }
        
        result = await products_collection.insert_one(new_product)
        self.write({"id": str(result.inserted_id)})

class ProductAPIHandler(tornado.web.RequestHandler):
    async def delete(self, product_id):
        result = await products_collection.delete_one({"_id": ObjectId(product_id)})
        if result.deleted_count > 0:
            self.write({"status": "deleted"})
        else:
            self.set_status(404)
            self.write({"error": "Product not found"})

# --- SETUP APP ---

def make_app():
    return tornado.web.Application([
        # Rotte Frontend
        (r"/", tornado.web.RedirectHandler, {"url": "/products"}),
        (r"/products", ProductListHandler),
        (r"/products/new", NewProductHandler),
        (r"/products/delete/([0-9a-fA-F]+)", DeleteProductHandler),
        (r"/products/toggle/([0-9a-fA-F]+)", ToggleProductHandler),

        # Rotte API
        (r"/api/products", ProductsAPIHandler),
        (r"/api/product/([0-9a-fA-F]+)", ProductAPIHandler),
    ], template_path="templates")

async def main(shutdown_event):
    app = make_app()
    app.listen(8888)
    print("Server attivo su http://localhost:8888/products")
    await shutdown_event.wait()
    print("Chiusura server...")

if __name__ == "__main__":
    shutdown_event = asyncio.Event()
    try:
        asyncio.run(main(shutdown_event))
    except KeyboardInterrupt:
        shutdown_event.set()