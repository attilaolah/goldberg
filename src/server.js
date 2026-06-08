const fs = require("fs");
const http = require("http");
const path = require("path");

const PORT = 5297;
const HOST = "127.0.0.1";
const ROOT_DIR = __dirname;

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
};

function getSafePath(requestUrl) {
  const pathname = new URL(requestUrl, `http://${HOST}:${PORT}`).pathname;
  const normalizedPath = path.normalize(pathname === "/" ? "/index.html" : pathname);
  const candidate = path.join(ROOT_DIR, normalizedPath);
  if (!candidate.startsWith(ROOT_DIR)) {
    return null;
  }
  return candidate;
}

const server = http.createServer((req, res) => {
  const filePath = getSafePath(req.url || "/");
  if (!filePath) {
    res.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Forbidden");
    return;
  }

  fs.readFile(filePath, (error, content) => {
    if (error) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("Not Found");
      return;
    }

    const extension = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      "Content-Type": contentTypes[extension] || "application/octet-stream",
    });
    res.end(content);
  });
});

server.listen(PORT, HOST, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
