import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

function readDraftList(dir: string) {
  if (!fs.existsSync(dir)) return [];
  const files = fs.readdirSync(dir);
  const draftsList = files
    .filter(file => file.endsWith('.json') && !file.startsWith('SoW-Draft-'))
    .map(file => {
      try {
        const filePath = path.join(dir, file);
        const stats = fs.statSync(filePath);
        const fileContent = fs.readFileSync(filePath, 'utf-8');
        const data = JSON.parse(fileContent);
        return {
          filename: file,
          name: data.project?.name || 'Untitled',
          customer: data.project?.customer || 'N/A',
          lastSaved: stats.mtime.toISOString()
        };
      } catch (e) {
        return null;
      }
    })
    .filter(Boolean) as { filename: string; name: string; customer: string; lastSaved: string }[];

  draftsList.sort((a, b) => new Date(b.lastSaved).getTime() - new Date(a.lastSaved).getTime());
  return draftsList;
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'save-draft-api',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          // POST /api/save-draft
          if (req.url === '/api/save-draft' && req.method === 'POST') {
            let body = '';
            req.on('data', (chunk) => {
              body += chunk;
            });
            req.on('end', () => {
              try {
                const { filename, data } = JSON.parse(body);
                const draftsDir = path.resolve(__dirname, 'drafts');
                if (!fs.existsSync(draftsDir)) {
                  fs.mkdirSync(draftsDir, { recursive: true });
                }
                const filePath = path.join(draftsDir, filename);
                fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
                
                res.statusCode = 200;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ success: true, filePath }));
              } catch (err: any) {
                res.statusCode = 500;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ error: err.message }));
              }
            });
            return;
          }

          // GET /api/list-drafts
          if (req.url === '/api/list-drafts' && req.method === 'GET') {
            try {
              const draftsDir = path.resolve(__dirname, 'drafts');
              res.statusCode = 200;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify(readDraftList(draftsDir)));
            } catch (err: any) {
              res.statusCode = 500;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ error: err.message }));
            }
            return;
          }

          // GET /api/list-archive
          if (req.url === '/api/list-archive' && req.method === 'GET') {
            try {
              const archiveDir = path.resolve(__dirname, 'archive');
              res.statusCode = 200;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify(readDraftList(archiveDir)));
            } catch (err: any) {
              res.statusCode = 500;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ error: err.message }));
            }
            return;
          }

          // GET /api/load-draft
          if (req.url?.startsWith('/api/load-draft') && req.method === 'GET') {
            try {
              const urlParams = new URL(req.url, `http://${req.headers.host}`);
              const filename = urlParams.searchParams.get('filename');
              if (!filename) {
                res.statusCode = 400;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ error: 'Filename query param required' }));
                return;
              }
              const filePath = path.resolve(__dirname, 'drafts', filename);
              // Prevent directory traversal
              if (!filePath.startsWith(path.resolve(__dirname, 'drafts'))) {
                res.statusCode = 403;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ error: 'Access denied' }));
                return;
              }
              if (!fs.existsSync(filePath)) {
                res.statusCode = 404;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ error: 'Draft not found' }));
                return;
              }
              const content = fs.readFileSync(filePath, 'utf-8');
              res.statusCode = 200;
              res.setHeader('Content-Type', 'application/json');
              res.end(content);
            } catch (err: any) {
              res.statusCode = 500;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ error: err.message }));
            }
            return;
          }

          // POST /api/delete-draft
          if (req.url === '/api/delete-draft' && req.method === 'POST') {
            let body = '';
            req.on('data', (chunk) => {
              body += chunk;
            });
            req.on('end', () => {
              try {
                const { filename } = JSON.parse(body);
                if (!filename) {
                  res.statusCode = 400;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'Filename body param required' }));
                  return;
                }
                const filePath = path.resolve(__dirname, 'drafts', filename);
                if (!filePath.startsWith(path.resolve(__dirname, 'drafts'))) {
                  res.statusCode = 403;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'Access denied' }));
                  return;
                }
                if (fs.existsSync(filePath)) {
                  fs.unlinkSync(filePath);
                }
                res.statusCode = 200;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ success: true }));
              } catch (err: any) {
                res.statusCode = 500;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ error: err.message }));
              }
            });
            return;
          }

          // POST /api/archive-draft
          if (req.url === '/api/archive-draft' && req.method === 'POST') {
            let body = '';
            req.on('data', (chunk) => {
              body += chunk;
            });
            req.on('end', () => {
              try {
                const { filename } = JSON.parse(body);
                if (!filename) {
                  res.statusCode = 400;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'Filename body param required' }));
                  return;
                }
                const draftsDir = path.resolve(__dirname, 'drafts');
                const archiveDir = path.resolve(__dirname, 'archive');
                const sourcePath = path.resolve(draftsDir, filename);
                const destPath = path.resolve(archiveDir, filename);
                if (!sourcePath.startsWith(draftsDir) || !destPath.startsWith(archiveDir)) {
                  res.statusCode = 403;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'Access denied' }));
                  return;
                }
                if (!fs.existsSync(sourcePath)) {
                  res.statusCode = 404;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'Draft not found' }));
                  return;
                }
                if (!fs.existsSync(archiveDir)) {
                  fs.mkdirSync(archiveDir, { recursive: true });
                }
                if (fs.existsSync(destPath)) {
                  res.statusCode = 409;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'A file with this name already exists in the archive.' }));
                  return;
                }
                fs.renameSync(sourcePath, destPath);
                res.statusCode = 200;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ success: true }));
              } catch (err: any) {
                res.statusCode = 500;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ error: err.message }));
              }
            });
            return;
          }

          // POST /api/unarchive-draft
          if (req.url === '/api/unarchive-draft' && req.method === 'POST') {
            let body = '';
            req.on('data', (chunk) => {
              body += chunk;
            });
            req.on('end', () => {
              try {
                const { filename } = JSON.parse(body);
                if (!filename) {
                  res.statusCode = 400;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'Filename body param required' }));
                  return;
                }
                const draftsDir = path.resolve(__dirname, 'drafts');
                const archiveDir = path.resolve(__dirname, 'archive');
                const sourcePath = path.resolve(archiveDir, filename);
                const destPath = path.resolve(draftsDir, filename);
                if (!sourcePath.startsWith(archiveDir) || !destPath.startsWith(draftsDir)) {
                  res.statusCode = 403;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'Access denied' }));
                  return;
                }
                if (!fs.existsSync(sourcePath)) {
                  res.statusCode = 404;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'Archived draft not found' }));
                  return;
                }
                if (!fs.existsSync(draftsDir)) {
                  fs.mkdirSync(draftsDir, { recursive: true });
                }
                if (fs.existsSync(destPath)) {
                  res.statusCode = 409;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ error: 'A draft with this name already exists. Rename or remove it before restoring this one.' }));
                  return;
                }
                fs.renameSync(sourcePath, destPath);
                res.statusCode = 200;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ success: true }));
              } catch (err: any) {
                res.statusCode = 500;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify({ error: err.message }));
              }
            });
            return;
          }

          next();
        });
      }
    }
  ],
})
