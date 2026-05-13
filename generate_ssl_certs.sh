#!/bin/bash

# SSL Certificate Generation Script for Face Data Collection App
# This script generates self-signed SSL certificates that work on all browsers including mobile devices

set -e  # Exit on any error

echo "🔐 Generating SSL certificates for Face Data Collection App..."

# Create certs directory if it doesn't exist
CERT_DIR="./certs"
mkdir -p "$CERT_DIR"

# Certificate configuration
DOMAIN="localhost"
IP="172.16.3.110" # "127.0.0.1"
COUNTRY="IN"
STATE="Karnataka"
CITY="Bangalore"
ORG="Face Data Collection"
ORG_UNIT="IT Department"
DAYS=3650  # 10 years validity

# Files
KEY_FILE="$CERT_DIR/key.pem"
CERT_FILE="$CERT_DIR/cert.pem"
CSR_FILE="$CERT_DIR/server.csr"
CONFIG_FILE="$CERT_DIR/openssl.conf"

echo "📁 Creating certificates in: $CERT_DIR"

# Create OpenSSL configuration file for better browser compatibility
cat > "$CONFIG_FILE" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
C=$COUNTRY
ST=$STATE
L=$CITY
O=$ORG
OU=$ORG_UNIT
CN=$DOMAIN

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
DNS.3 = 127.0.0.1
DNS.4 = ::1
IP.1 = 127.0.0.1
IP.2 = ::1
IP.3 = 0.0.0.0
EOF

# Generate private key
echo "🔑 Generating private key..."
openssl genrsa -out "$KEY_FILE" 2048

# Generate certificate signing request
echo "📝 Generating certificate signing request..."
openssl req -new -key "$KEY_FILE" -out "$CSR_FILE" -config "$CONFIG_FILE"

# Generate self-signed certificate
echo "📜 Generating self-signed certificate..."
openssl x509 -req -in "$CSR_FILE" -signkey "$KEY_FILE" -out "$CERT_FILE" -days "$DAYS" -extensions v3_req -extfile "$CONFIG_FILE"

# Set proper permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

# Clean up CSR and config files
rm "$CSR_FILE" "$CONFIG_FILE"

echo "✅ SSL certificates generated successfully!"
echo ""
echo "📂 Certificate files:"
echo "   Private Key: $KEY_FILE"
echo "   Certificate: $CERT_FILE"
echo ""
echo "⚠️  Browser Security Notice:"
echo "   Since this is a self-signed certificate, browsers will show a security warning."
echo "   For development purposes, you can safely proceed by:"
echo ""
echo "   🔹 Chrome/Edge: Click 'Advanced' → 'Proceed to localhost (unsafe)'"
echo "   🔹 Firefox: Click 'Advanced' → 'Accept the Risk and Continue'"
echo "   🔹 Safari: Click 'Show Details' → 'visit this website'"
echo "   🔹 Mobile browsers: Similar process - look for 'Advanced' or 'Details'"
echo ""
echo "📱 For mobile devices:"
echo "   1. Connect to the same WiFi network as your server"
echo "   2. Find your server's IP address using: ip addr show"
echo "   3. Access https://YOUR_IP_ADDRESS:8888"
echo "   4. Accept the security warning on your mobile browser"
echo ""
echo "🔧 To add your IP address to the certificate, edit this script and:"
echo "   1. Add your IP to the IP.3, IP.4 lines in the alt_names section"
echo "   2. Run the script again"
echo ""
echo "🚀 Ready to start your HTTPS server!"
