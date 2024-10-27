import os
import fitz
from datetime import datetime

def process_pdf(pdf_path, upload_folder):
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    pdf_file = fitz.open(pdf_path)
    page = pdf_file[0]  # Get only the first page
    images = list(page.get_images(full=True))
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    if len(images) == 1:
        img = images[0]
        xref = img[0]
        base_image = pdf_file.extract_image(xref)
        image_bytes = base_image["image"]
        image_save_path = os.path.join(upload_folder, f"image_{timestamp}.jpeg")
        with open(image_save_path, "wb") as image_file:
            image_file.write(image_bytes)
    else:
        # If no images found, save the first page as an image
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
        image_save_path = os.path.join(upload_folder, f"image_{timestamp}.jpeg")
        pix.save(image_save_path)

    pdf_file.close()
    return image_save_path
'''
if __name__ == "__main__":
    pdf_path = "uploads/Bka Ppt 2021-31.pdf"  # Path to your PDF file
    upload_folder = "uploads"  # Folder to save extracted images

    try:
        # Process the PDF to extract the first page or image
        extracted_image_path = process_pdf(pdf_path, upload_folder)
        print(f"Extracted image saved at: {extracted_image_path}")

    except Exception as e:
        print(f"An error occurred: {e}")
 '''  