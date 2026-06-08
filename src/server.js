const fs = require("fs");
const http = require("http");
const path = require("path");

const PORT = 5297;
const HOST = "127.0.0.1";
const htmlPath = path.join(__dirname, "index.html");
const html = fs.readFileSync(htmlPath, "utf8");

const server = http.createServer((_req, res) => {
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(html);
});

server.listen(PORT, HOST, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
