FROM node:20-alpine AS build

WORKDIR /app

COPY client/package.json client/package-lock.json* client/pnpm-lock.yaml* client/yarn.lock* ./
RUN npm ci || npm i

ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

COPY client/ ./
RUN npm run build

# ---------- Run stage (Nginx) ----------
FROM nginx:alpine

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]