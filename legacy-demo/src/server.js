const http = require("http");
const path = require("path");
const fs = require("fs");
const { URL } = require("url");
const { createStore } = require("./data-store");

const PORT = Number(process.env.PORT || 4100);
const store = createStore();

const sendJson = (res, statusCode, payload) => {
  res.writeHead(statusCode, { "Content-Type": "application/json" });
  res.end(JSON.stringify(payload, null, 2));
};

const readBody = req =>
  new Promise((resolve, reject) => {
    let body = "";
    req.on("data", chunk => {
      body += chunk;
    });
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        reject(new Error("request body must be valid JSON"));
      }
    });
    req.on("error", reject);
  });

const serveStatic = (res, fileName) => {
  const filePath = path.join(__dirname, "..", "public", fileName);
  fs.createReadStream(filePath)
    .on("error", () => sendJson(res, 404, { error: "not found" }))
    .pipe(res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }));
};

const handle = async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  try {
    if (req.method === "GET" && url.pathname === "/") {
      return serveStatic(res, "index.html");
    }

    if (req.method === "GET" && url.pathname === "/api/products") {
      return sendJson(res, 200, {
        products: store.listProducts({
          category: url.searchParams.get("category"),
          search: url.searchParams.get("search")
        })
      });
    }

    if (req.method === "POST" && url.pathname === "/api/sessions") {
      return sendJson(res, 201, store.createSession(await readBody(req)));
    }

    if (req.method === "GET" && url.pathname === "/api/cart") {
      return sendJson(res, 200, store.getCart(url.searchParams.get("sessionId")));
    }

    if (req.method === "POST" && url.pathname === "/api/cart/items") {
      return sendJson(res, 200, store.addCartItem(await readBody(req)));
    }

    if (req.method === "POST" && url.pathname === "/api/checkout") {
      return sendJson(res, 201, { order: store.checkout(await readBody(req)) });
    }

    if (req.method === "GET" && url.pathname === "/api/admin/orders") {
      return sendJson(res, 200, { orders: store.listOrders() });
    }

    return sendJson(res, 404, { error: "not found" });
  } catch (error) {
    return sendJson(res, 400, { error: error.message });
  }
};

if (require.main === module) {
  http.createServer(handle).listen(PORT, () => {
    console.log(`E-commerce project running on http://localhost:${PORT}`);
  });
}

module.exports = handle;
