FROM python:3.12

WORKDIR /app

RUN apt-get update &&  apt-get install -y nodejs npm

# Install Vercel CLI globally
RUN npm install -g vercel
