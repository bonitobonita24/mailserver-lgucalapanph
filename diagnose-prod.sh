#!/bin/bash
# Diagnostic script for Mailu Mail Server in Dokploy production

echo "=== Checking Docker Containers Status ==="
docker ps -a | grep -E "mailu|mail"

echo -e "\n=== Checking Dokploy Network ==="
docker network ls | grep dokploy

echo -e "\n=== Checking if containers are on dokploy-network ==="
docker network inspect dokploy-network | grep -A 5 "Containers"

echo -e "\n=== Checking Mailu Front Container Logs (last 50 lines) ==="
docker logs --tail 50 $(docker ps -aqf "name=mailu-front" 2>/dev/null || docker ps -aqf "name=front" 2>/dev/null || echo "")

echo -e "\n=== Checking Mailu Admin Container Logs (last 50 lines) ==="
docker logs --tail 50 $(docker ps -aqf "name=mailu-admin" 2>/dev/null || docker ps -aqf "name=admin" 2>/dev/null || echo "")

echo -e "\n=== Checking Traefik Logs (last 30 lines) ==="
docker logs --tail 30 $(docker ps -qf "name=traefik")

echo -e "\n=== Checking Port Bindings ==="
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep -E "mailu|mail"

echo -e "\n=== Disk Space ==="
df -h | grep -E "Filesystem|/dev/"

echo -e "\n=== Memory Usage ==="
free -h
