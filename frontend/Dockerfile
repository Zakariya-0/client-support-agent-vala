# --- Étape 1 : build de l'application React ---
FROM node:18-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --fetch-timeout=120000 --fetch-retries=5 --no-audit --no-fund

COPY . .

# create-react-app fige les variables REACT_APP_* au moment du build (pas à l'exécution)
ARG REACT_APP_API_URL=http://localhost:8000
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

# --- Étape 2 : service des fichiers statiques par nginx ---
FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80
