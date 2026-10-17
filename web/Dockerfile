# Dev container (PRD §2.2): vite dev server with /api proxied to the api
# service. A static production build is `npm run build` → web/dist.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
