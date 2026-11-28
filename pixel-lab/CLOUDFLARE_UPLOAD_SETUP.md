# Cloudflare R2 setup for Pixel Lab uploads

The GitHub Pages gallery is static. Persistent uploads use a separate Cloudflare Worker and R2 bucket.

1. Create an R2 bucket named `ashur-reference-library`.
2. Create a Worker named `ashur-reference-library` and paste the source from `cloudflare-reference-worker.js`.
3. Add an R2 binding: variable `ASHUR_REFERENCES` → bucket `ashur-reference-library`.
4. Add a Worker secret named `UPLOAD_TOKEN` with a long random value. Do not commit this secret or paste it into source code.
5. Deploy the Worker. Copy its `workers.dev` URL.
6. Open Pixel Lab → Референсы → Загрузить. Enter the Worker URL and secret. They are kept in session storage in that browser session.

Images are public to view once uploaded; only upload is protected by the secret. Supported: PNG/JPG/WEBP/GIF, maximum 10 MB per file. The Worker CORS allowlist is the GitHub Pages origin.
