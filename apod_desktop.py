""" 
group members: Nadirsha T Karee , Joy Asher
COMP 593 - Final Project

Description: 
  Downloads NASA's Astronomy Picture of the Day (APOD) from a specified date
  and sets it as the desktop background image.

Usage:
  python apod_desktop.py [apod_date]

Parameters:
  apod_date = APOD date (format: YYYY-MM-DD)
"""
from datetime import date
import sqlite3
import hashlib
import os
import re
import image_lib
import apod_api
import sys

# Full paths of the image cache folder and database
# - The image cache directory is a subdirectory of the specified parent directory.
# - The image cache database is a sqlite database located in the image cache directory.
script_dir = os.path.dirname(os.path.abspath(__file__))
image_cache_dir = os.path.join(script_dir, 'images')
image_cache_db = os.path.join(image_cache_dir, 'image_cache.db')

def main():
    # Get the APOD date from the command line
    apod_date = get_apod_date()    

    # Initialize the image cache
    init_apod_cache()

    # Add the APOD for the specified date to the cache
    apod_id = add_apod_to_cache(apod_date)

    # Get the information for the APOD from the DB
    apod_info = get_apod_info(apod_id)

    # Set the APOD as the desktop background image
    image_lib.set_desktop_background_image(apod_info['file_path'])

def get_apod_date():
    """Gets the APOD date
     
    The APOD date is taken from the first command line parameter.
    Validates that the command line parameter specifies a valid APOD date.
    Prints an error message and exits script if the date is invalid.
    Uses today's date if no date is provided on the command line.

    Returns:
        date: APOD date
    """
    num_params = len(sys.argv) - 1
    if num_params >= 1:
        # Date parameter has been provided, so get it
        try:
            apod_date = date.fromisoformat(sys.argv[1])
        except ValueError as err:
            print(f'Error: Invalid date format; {err}')
            sys.exit('Script execution aborted')

        # Validate that the date is within range
        MIN_APOD_DATE = date.fromisoformat("1995-06-16")
        if apod_date < MIN_APOD_DATE:
            print(f'Error: Date too far in past; First APOD was on {MIN_APOD_DATE.isoformat()}')
            sys.exit('Script execution aborted')
        elif apod_date > date.today():
            print('Error: APOD date cannot be in the future')
            sys.exit('Script execution aborted')
    else:
        # No date parameter has been provided, so use today's date
        apod_date = date.today()
    
    return apod_date

def init_apod_cache():
    """Initializes the image cache by:
    - Creating the image cache directory if it does not already exist,
    - Creating the image cache database if it does not already exist.
    """
    # Create the image cache directory if it does not already exist
    # You should know what to do here as demonstrated in previous labs
    if not os.path.exists(image_cache_dir):
        os.makedirs(image_cache_dir)

    # Create the DB if it does not already exist
    #Complete this with the correct instructions
    db_cxn = sqlite3.connect(image_cache_db)
    db_cursor = db_cxn.cursor()

    # Create the image_data table if it doesn't exist
    create_db_query = """
        CREATE TABLE IF NOT EXISTS image_data 
        (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            explanation TEXT NOT NULL,
            file_path TEXT NOT NULL,
            sha256 TEXT NOT NULL
        );
    """
    db_cursor.execute(create_db_query)
    db_cxn.commit()
    db_cxn.close()


def add_apod_to_cache(apod_date):
    """Adds the APOD image from a specified date to the image cache.
     
    The APOD information and image file is downloaded from the NASA API.
    If the APOD is not already in the DB, the image file is saved to the 
    image cache and the APOD information is added to the image cache DB.

    Args:
        apod_date (date): Date of the APOD image

    Returns:
        int: Record ID of the APOD in the image cache DB, if a new APOD is added to the
        cache successfully or if the APOD already exists in the cache. Zero, if unsuccessful.
    """
    print("APOD date:", apod_date.isoformat())

    # Download the APOD information from the NASA API
    apod_info = apod_api.get_apod_info(apod_date)
    if apod_info is None: return 0
    apod_title = apod_info['title']
    print("APOD title:", apod_title)

    # Download the APOD image
    apod_url = apod_info['url']
    apod_image_data = image_lib.download_image(apod_url)
    if apod_image_data is None: return 0
    print("Downloaded image from " + apod_url)
    
    # Check whether the APOD already exists in the image cache
    apod_sha256 = hashlib.sha256(apod_image_data).hexdigest()
    print("APOD SHA-256:", apod_sha256)
    apod_id = get_apod_id_from_db(apod_sha256)
    if apod_id != 0: 
        return apod_id

    # Save the APOD file to the image cache directory
    apod_path = determine_apod_file_path(apod_title, apod_url)
    print("APOD file path:", apod_path)
    if not image_lib.save_image_file(apod_image_data, apod_path): return 0
    
    # Add the APOD information to the DB
    apod_explanation = apod_info['explanation']
    apod_id = add_apod_to_db(apod_title, apod_explanation, apod_path, apod_sha256)
    return apod_id

def add_apod_to_db(title, explanation, file_path, sha256):
    """Adds specified APOD information to the image cache DB.
     
    Args:
        title (str): Title of the APOD image
        explanation (str): Explanation of the APOD image
        file_path (str): Full path of the APOD image file
        sha256 (str): SHA-256 hash value of APOD image

    Returns:
        int: The ID of the newly inserted APOD record, if successful. Zero, if unsuccessful       
    """
    print("Adding APOD to image cache DB...", end='')
    try:
        db_cxn = sqlite3.connect(image_cache_db)
        db_cursor = db_cxn.cursor()
        insert_image_query = """
            INSERT INTO image_data 
            (title, explanation, file_path, sha256)
            VALUES (?, ?, ?, ?);"""
        image_data = (title, explanation, file_path, sha256.upper())
        db_cursor.execute(insert_image_query, image_data)
        db_cxn.commit()
        print("success")
        db_cxn.close()
        return db_cursor.lastrowid
    except:
        print("failure")
        return 0

def get_apod_id_from_db(image_sha256):
    """Gets the record ID of the APOD in the cache having a specified SHA-256 hash value
    
    This function can be used to determine whether a specific image exists in the cache.

    Args:
        image_sha256 (str): SHA-256 hash value of APOD image

    Returns:
        int: Record ID of the APOD in the image cache DB, if it exists. Zero, if it does not.
    """
    db_cxn = sqlite3.connect(image_cache_db)
    db_cursor = db_cxn.cursor()

    # Query DB for image with same hash value as image in response message
    #db_cursor.execute("SELECT id FROM image_data WHERE sha256='" + image_sha256.upper() + "'")
    #db_cursor.execute("SELECT id FROM image_data WHERE sha256=?;", [image_sha256.upper()])
    db_cursor.execute("SELECT id FROM image_data WHERE sha256=?;", (image_sha256.upper(),))
    query_results = db_cursor.fetchone()
    db_cxn.close()

    # Output message and result indicating whether image is already in the cache
    if query_results is not None:
        print("APOD image is already in cache.")
        return query_results[0]
    else:
        print("APOD image is not already in cache.")
        return 0

def determine_apod_file_path(image_title, image_url):
    """Determines the path at which a newly downloaded APOD image must be 
    saved in the image cache. 
    
    The image file name is constructed as follows:
    - The file extension is taken from the image URL
    - The file name is taken from the image title, where:
        - Leading and trailing spaces are removed
        - Inner spaces are replaced with underscores
        - Characters other than letters, numbers, and underscores are removed

    For example, suppose:
    - The image cache directory path is 'C:\\temp\\APOD'
    - The image URL is 'https://apod.nasa.gov/apod/image/2205/NGC3521LRGBHaAPOD-20.jpg'
    - The image title is ' NGC #3521: Galaxy in a Bubble '

    The image path will be 'C:\\temp\\APOD\\NGC_3521_Galaxy_in_a_Bubble.jpg'

    Args:
        image_title (str): APOD title
        image_url (str): APOD image URL
    
    Returns:
        str: Full path at which the APOD image file must be saved in the image cache directory
    """
    # Extract the file extension from the URL
    file_ext = image_url.split(".")[-1]

    # Remove leading and trailing spaces from the title
    file_name = image_title.strip()

    # Replace inner spaces with underscores
    file_name = file_name.replace(' ', '_')
    
    # Remove any non-word characters
    file_name = re.sub(r'\W+', '', file_name)
    
    # Append the extension to the file name
    file_name = '.'.join((file_name, file_ext))
    
    # Joint the directory path and file name to get the full path
    file_path = os.path.join(image_cache_dir, file_name)
    
    return file_path

def get_apod_info(image_id):
    """Gets the title, explanation, and full path of the APOD having a specified
    ID from the DB.

    Args:
        image_id (int): ID of APOD in the DB

    Returns:
        dict: Dictionary of APOD information
        (Dictionary keys: 'title', 'explanation', 'file_path')
    """
    # Query DB for image info
    db_cxn = sqlite3.connect(image_cache_db)
    db_cursor = db_cxn.cursor()
    image_path_query = """SELECT title, explanation, file_path FROM image_data WHERE id=?;"""
    
    db_cursor.execute(image_path_query,(image_id,))
    query_result = db_cursor.fetchone()
    db_cxn.close()

    # Put information into a dictionary
    #Fill this out
    apod_info = {
        'title': query_result[0],
        'explanation': query_result[1],
        'file_path': query_result[2]
    }

    return apod_info

def get_all_apod_titles():
    """Gets a list of the titles of all APODs in the image cache

    Returns:
        list: Titles of all images in the cache
    """
    db_cxn = sqlite3.connect(image_cache_db)
    
    db_cursor = db_cxn.cursor()
    image_titles_query = """SELECT title FROM image_data;"""
    db_cursor.execute(image_titles_query)
    image_titles = db_cursor.fetchall()
    db_cxn.close()

    return tuple([t[0] for t in image_titles])

if __name__ == '__main__':
    main() 