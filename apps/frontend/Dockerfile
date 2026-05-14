FROM node:20-alpine

WORKDIR /app

COPY apps/frontend/package.json ./
RUN npm install

COPY apps/frontend ./

RUN npm run build

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "4173"]
