const crypto = require("crypto");

const money = value => Number(value.toFixed(2));

const createStore = () => {
  const products = [
    {
      id: "sku-cloud-hoodie",
      name: "Cloud Ops Hoodie",
      category: "apparel",
      price: 54.99,
      inventory: 14,
      tags: ["aws", "cotton", "unisex"]
    },
    {
      id: "sku-api-notebook",
      name: "API Design Notebook",
      category: "stationery",
      price: 18.5,
      inventory: 32,
      tags: ["planning", "paper"]
    },
    {
      id: "sku-deploy-kit",
      name: "Deployment Desk Kit",
      category: "hardware",
      price: 89,
      inventory: 6,
      tags: ["workflow", "tools"]
    }
  ];

  const users = new Map();
  const carts = new Map();
  const orders = [];

  const listProducts = filters => {
    const category = filters.category && filters.category.toLowerCase();
    const search = filters.search && filters.search.toLowerCase();

    return products.filter(product => {
      const categoryMatch = !category || product.category === category;
      const searchMatch =
        !search ||
        product.name.toLowerCase().includes(search) ||
        product.tags.some(tag => tag.includes(search));

      return categoryMatch && searchMatch;
    });
  };

  const createSession = ({ email, name }) => {
    if (!email || !name) {
      throw new Error("name and email are required");
    }

    const sessionId = crypto.randomUUID();
    users.set(sessionId, { id: sessionId, email, name });
    carts.set(sessionId, []);

    return { sessionId, user: users.get(sessionId) };
  };

  const ensureSession = sessionId => {
    if (!users.has(sessionId)) {
      throw new Error("valid sessionId is required");
    }
  };

  const getCart = sessionId => {
    ensureSession(sessionId);
    const items = carts.get(sessionId).map(item => {
      const product = products.find(candidate => candidate.id === item.productId);
      return {
        productId: item.productId,
        name: product.name,
        quantity: item.quantity,
        unitPrice: product.price,
        lineTotal: money(product.price * item.quantity)
      };
    });

    const subtotal = money(
      items.reduce((total, item) => total + item.lineTotal, 0)
    );
    const tax = money(subtotal * 0.0725);
    const shipping = subtotal >= 75 || subtotal === 0 ? 0 : 7.99;

    return {
      sessionId,
      items,
      totals: {
        subtotal,
        tax,
        shipping,
        grandTotal: money(subtotal + tax + shipping)
      }
    };
  };

  const addCartItem = ({ sessionId, productId, quantity }) => {
    ensureSession(sessionId);
    const product = products.find(candidate => candidate.id === productId);
    const count = Number(quantity);

    if (!product) {
      throw new Error("product not found");
    }

    if (!Number.isInteger(count) || count <= 0) {
      throw new Error("quantity must be a positive integer");
    }

    if (count > product.inventory) {
      throw new Error("requested quantity exceeds available inventory");
    }

    const cart = carts.get(sessionId);
    const existing = cart.find(item => item.productId === productId);

    if (existing) {
      const nextQuantity = existing.quantity + count;
      if (nextQuantity > product.inventory) {
        throw new Error("cart quantity exceeds available inventory");
      }
      existing.quantity = nextQuantity;
    } else {
      cart.push({ productId, quantity: count });
    }

    return getCart(sessionId);
  };

  const checkout = ({ sessionId, address }) => {
    ensureSession(sessionId);
    if (!address) {
      throw new Error("shipping address is required");
    }

    const cart = getCart(sessionId);
    if (!cart.items.length) {
      throw new Error("cart is empty");
    }

    for (const item of cart.items) {
      const product = products.find(candidate => candidate.id === item.productId);
      if (item.quantity > product.inventory) {
        throw new Error(`${product.name} is no longer available`);
      }
    }

    for (const item of cart.items) {
      const product = products.find(candidate => candidate.id === item.productId);
      product.inventory -= item.quantity;
    }

    const order = {
      id: `ord-${String(orders.length + 1).padStart(4, "0")}`,
      sessionId,
      user: users.get(sessionId),
      address,
      items: cart.items,
      totals: cart.totals,
      status: "submitted",
      createdAt: new Date().toISOString()
    };

    orders.push(order);
    carts.set(sessionId, []);

    return order;
  };

  return {
    listProducts,
    createSession,
    getCart,
    addCartItem,
    checkout,
    listOrders: () => orders
  };
};

module.exports = { createStore, money };
