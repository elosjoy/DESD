from decimal import Decimal

from .models import Product


# session-based cart - stores items in the user's session rather than the database
class Cart:
    SESSION_KEY = "cart"

    def __init__(self, request):
        # store the cart in the session
        self.session = request.session
        cart = self.session.get(self.SESSION_KEY)
        if cart is None:
            cart = {}
            self.session[self.SESSION_KEY] = cart
        self.cart = cart

    def save(self):
        # mark the session as modified so Django saves it
        self.session.modified = True

    def _normalize_quantity(self, quantity):
        # clamp to at least 1
        quantity_value = int(quantity)
        if quantity_value < 1:
            return 1
        return quantity_value

    def add(self, product, quantity=1, override_quantity=False):
        # use string id as the key so it's JSON serialisable
        product_id = str(product.id)
        quantity_value = self._normalize_quantity(quantity)

        if product_id not in self.cart:
            self.cart[product_id] = {"quantity": 0, "price": str(product.price)}

        if override_quantity:
            self.cart[product_id]["quantity"] = quantity_value
        else:
            self.cart[product_id]["quantity"] += quantity_value

        self.save()

    def remove(self, product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def __iter__(self):
        # look up the actual Product objects so templates can use them
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)

        cart_copy = self.cart.copy()
        for product in products:
            cart_copy[str(product.id)]["product"] = product

        for item in cart_copy.values():
            item["price"] = Decimal(item["price"])
            item["total_price"] = item["price"] * item["quantity"]
            yield item

    def __len__(self):
        return sum(item["quantity"] for item in self.cart.values())

    def get_total_items(self):
        return len(self)

    def get_total_price(self):
        return sum(Decimal(item["price"]) * item["quantity"] for item in self.cart.values())

    def clear(self):
        # remove the cart from the session
        self.session.pop(self.SESSION_KEY, None)
        self.save()

    def clear_cart(self):
        self.clear()
