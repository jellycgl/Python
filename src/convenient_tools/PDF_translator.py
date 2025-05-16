# from reportlab.lib.pagesizes import letter
# from reportlab.lib.units import inch
# from reportlab.pdfgen import canvas

# # List of image file paths
# image_files = [
#     r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate - Page 1.jpg',
#     r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate - Page 2.jpg', 
#     r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate - Page 3.jpg'
# ]

# # Output PDF file path
# output_pdf = r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate - Guangzu Chen.pdf'

# # Create a canvas with letter size page dimensions
# c = canvas.Canvas(output_pdf, pagesize=letter)

# # Iterate over the image files
# for image_file in image_files:
#     # Draw the image on the canvas
#     c.drawImage(image_file, 0, 0, width=8.5 * inch, height=11 * inch)

#     # Add a new page for the next image
#     c.showPage()

# # Save and close the PDF
# c.save()

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# List of image file paths
# image_files = [
#     r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate - Page 1.jpg',
#     r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate - Page 2.jpg', 
#     r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate - Page 3.jpg'
# ]

# image_files = [
#     r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Marriage Certificate - Page 1.jpg',
#     r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Marriage Certificate - Page 2.jpg'
# ]

image_files = [
    r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate(Runmei Zhang) - Page 1.jpg',
    r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate(Runmei Zhang) - Page 2.jpg',
    r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate(Runmei Zhang) - Page 3.jpg'
]

# Output PDF file path
output_pdf = r'C:\Users\GuoliangChen\Desktop\Super Visa\探亲签证\Prepare\Retirement Certificate - Runmei Zhang.pdf'

# Create a new PDF canvas
pdf_canvas = canvas.Canvas(output_pdf, pagesize=letter)

# Iterate over the image files
for image_file in image_files:
    # Load the image using ImageReader
    image = ImageReader(image_file)

    # Get the dimensions of the image
    image_width, image_height = image.getSize()

    # Add a new page to the PDF canvas with the same dimensions as the image
    pdf_canvas.setPageSize((image_width, image_height))
    pdf_canvas.showPage()

    # Draw the image on the current page of the PDF canvas
    pdf_canvas.drawImage(image, 0, 0, width=image_width, height=image_height)

# Save the PDF file
pdf_canvas.save()

