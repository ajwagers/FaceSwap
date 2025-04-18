import http.server
import ssl
import socketserver
import os
import json
import csv # For writing CSV data
import datetime # For timestamps
import base64 # For decoding image data URL
import re # For cleaning filenames
from urllib.parse import urlparse

# --- Configuration ---
SERVER_ADDRESS = "0.0.0.0"
PORT = 8443 # Or your chosen port
CERT_FILE = "localhost+2.pem" # Or your cert filename
KEY_FILE = "localhost+2-key.pem" # Or your key filename
SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIRECTORY = os.path.join(SCRIPT_DIRECTORY, "images")
# --- New Paths ---
SWAPPED_IMAGES_DIR = os.path.join(SCRIPT_DIRECTORY, "swapped_images") # Folder for saved swaps
REGISTRATIONS_CSV = os.path.join(SCRIPT_DIRECTORY, "registrations.csv") # CSV file path
# --- End New Paths ---
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
# --- End Configuration ---

# --- Create Directories/Files if they don't exist ---
if not os.path.exists(IMAGES_DIRECTORY):
    print(f"Creating images directory: {IMAGES_DIRECTORY}")
    os.makedirs(IMAGES_DIRECTORY)
# --- New Directory Creation ---
if not os.path.exists(SWAPPED_IMAGES_DIR):
    print(f"Creating swapped images directory: {SWAPPED_IMAGES_DIR}")
    os.makedirs(SWAPPED_IMAGES_DIR)
# --- New CSV Header Check ---
if not os.path.isfile(REGISTRATIONS_CSV):
    print(f"Creating registrations CSV file: {REGISTRATIONS_CSV}")
    with open(REGISTRATIONS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'firstname', 'lastname', 'org_file','created_file']) # Write header
# --- End Directory/File Creation ---


# Custom Request Handler
class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def list_directory(self, path):
        self.send_error(404, "Not Found")
        return None

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path_segments = parsed_path.path.strip('/').split('/')

        if path_segments == ['api', 'images']:
            try:
                image_files = []
                if os.path.isdir(IMAGES_DIRECTORY):
                    for filename in os.listdir(IMAGES_DIRECTORY):
                        if os.path.isfile(os.path.join(IMAGES_DIRECTORY, filename)):
                            _, ext = os.path.splitext(filename)
                            if ext.lower() in ALLOWED_IMAGE_EXTENSIONS:
                                image_files.append(filename)
                    image_files.sort()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(image_files).encode('utf-8'))
            except Exception as e:
                print(f"Error listing images: {e}")
                self.send_error(500, f"Server error listing images: {e}")
            return

        # Serve files from /images or /swapped_images directories correctly
        if path_segments and path_segments[0] in ['images', 'swapped_images']:
             pass # Let parent handle after CWD is set

        super().do_GET()

    # --- New do_POST method ---
    def do_POST(self):
        parsed_path = urlparse(self.path)

        # --- API Endpoint: /api/save_swap ---
        if parsed_path.path == '/api/save_swap':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))

                # --- Validate Input ---
                first_name = data.get('firstName')
                last_name = data.get('lastName')
                image_data_url = data.get('imageDataUrl')

                if not first_name or not last_name or not image_data_url:
                    self.send_response(400)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Missing required fields (firstName, lastName, imageDataUrl)"}).encode('utf-8'))
                    return

                # --- 1. Save to CSV ---
                timestamp = datetime.datetime.now().isoformat()
                

                # --- 2. Save Image ---
                try:
                    # Clean names for filename (basic cleaning)
                    first_name_clean = re.sub(r'[^\w\-]+', '', first_name)
                    last_name_clean = re.sub(r'[^\w\-]+', '', last_name)
                    filename = f"{last_name_clean}-{first_name_clean}.png" # Assume PNG output
                    filepath = os.path.join(SWAPPED_IMAGES_DIR, filename)

                    # Decode Base64 Data URL (e.g., "data:image/png;base64,iVBOR...")
                    header, encoded = image_data_url.split(",", 1)
                    image_data = base64.b64decode(encoded)

                    # Write image file
                    with open(filepath, 'wb') as f:
                        f.write(image_data)
                    print(f"Saved image: {filepath}")

                except Exception as img_err:
                    print(f"Error saving image: {img_err}")
                    # Send error response if image saving fails
                    self.send_response(500)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": f"Error saving image: {img_err}"}).encode('utf-8'))
                    return
                try:
                    # Extract the filename from the image_data_url
                    chosen_image_filename = os.path.basename(image_data_url)

                    # Save the data to the CSV
                    with open(REGISTRATIONS_CSV, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        # Add the chosen image filename and output image filename to the CSV row
                        writer.writerow([timestamp, first_name, last_name, chosen_image_filename, filename])
                    print(f"Appended to CSV: {timestamp}, {first_name}, {last_name}, {chosen_image_filename}, {filename}")
                except Exception as csv_err:
                    print(f"Error writing to CSV: {csv_err}")
                    # Decide if this is fatal or just log it
                    # For now, we'll continue to try saving the image
                # --- Success Response ---
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Swap saved successfully.", "filename": filename}).encode('utf-8'))

            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Invalid JSON data"}).encode('utf-8'))
            except Exception as e:
                print(f"Error processing /api/save_swap: {e}")
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": f"Internal server error: {e}"}).encode('utf-8'))
            return

        # Handle other POST requests if needed, otherwise send error
        else:
            self.send_error(404, "Not Found")
    # --- End do_POST method ---

# --- Server Setup --- (Rest is the same as before)
os.chdir(SCRIPT_DIRECTORY)
print(f"Serving files from: {SCRIPT_DIRECTORY}")
httpd = socketserver.TCPServer((SERVER_ADDRESS, PORT), CustomHandler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
try:
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
except FileNotFoundError:
    print("\n" + "="*40 + "\nERROR: Certificate or key file not found!\n" + "="*40)
    exit(1)
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
print(f"Serving HTTPS on {SERVER_ADDRESS} port {PORT}...")
print(f"Serving images from: {IMAGES_DIRECTORY}")
print(f"Saving swapped images to: {SWAPPED_IMAGES_DIR}")
print(f"Logging registrations to: {REGISTRATIONS_CSV}")
print(f"API endpoints: /api/images (GET), /api/save_swap (POST)")
print("-" * 30)
print(f"Access locally: https://localhost:{PORT}")
print(f"Access on network: https://<YOUR_IP>:{PORT}")
print("-" * 30)
print("Waiting for connections... Press Ctrl+C to stop.")
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServer stopped.")
    httpd.server_close()
