const http = require("http");

const PORT = 5297;
const HOST = "127.0.0.1";

const html = "<!doctype html><html><head><title>Hello</title></head><body>Hello, World</body></html>";

const server = http.createServer((_req, res) => {
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(html);
});

server.listen(PORT, HOST, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
