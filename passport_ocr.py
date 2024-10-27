import os
import string as st
from dateutil import parser
import matplotlib.image as mpimg
import cv2
from passporteye import read_mrz
import json
import easyocr
import datetime
import re
from city_extraction import extract_text_from_image, preprocess_text, extract_cities_and_states

reader = easyocr.Reader(['en'])

def generate_timestamp_filename(prefix='tmp', extension='.png'):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}{extension}"

def parse_date(string, is_dob=True):
    date = parser.parse(string, yearfirst=True).date()
    current_year = datetime.datetime.now().year
    if is_dob and date.year > current_year:
        date = date.replace(year=date.year - 100)
    return date.strftime('%d/%m/%Y')

def clean(string):
    return ''.join(i for i in string if i.isalnum()).upper()

def get_country_name(country_code):
    if '1' in country_code:
        country_code = country_code.replace('1', 'I')
    return country_code

def get_gender(code):
    if code in ['M','m', 'F', 'f']:
        sex = code.upper()
    elif code == '0':
        sex = 'M'
    else:
        sex = 'F'
    return sex

def parse_mrz_lines(line1, line2):
    user_info = {}

    # Line 1
    passport_type = clean(line1[0]) if line1 and line1.strip() else 'P'
    user_info['passport_type'] = passport_type if passport_type in ['P'] else 'P'
    user_info['issuing_country'] = get_country_name(clean(line1[2:5]))
    surname_names = line1[5:44].split('<<', 1)
    if len(surname_names) < 2:
        surname_names += [' ']
    surname, names = surname_names
    user_info['surname'] = surname.replace('<', ' ').strip().upper()
    user_info['name'] = names.replace('<', ' ').strip().upper()
    user_info['name'] = re.sub(r'K{2,}', '', user_info['name'])
    user_info['name'] = re.sub(r'\d+', '', user_info['name'])
    
    # New condition: If name is empty, process surname
    if not user_info['name']:
        surname_words = user_info['surname'].split()
        if len(surname_words) == 3:
            user_info['name'] = surname_words[1]
            user_info['surname'] = f"{surname_words[0]} {surname_words[2]}"
        elif len(surname_words) == 2:
            user_info['name'] = surname_words[0]
            user_info['surname'] = surname_words[1]
    
    # Line 2
    passport_number = clean(line2[0:9])
    
    if passport_number[0] == '2':
        passport_number = 'Z' + passport_number[1:]
    elif passport_number[0] == '5':
        passport_number = 'S' + passport_number[1:]
    
    user_info['passport_number'] = passport_number
    user_info['nationality'] = get_country_name(clean(line2[10:13]))
    user_info['date_of_birth'] = parse_date(line2[13:19], is_dob=True)
    user_info['gender'] = get_gender(clean(line2[20]))
    user_info['expiration_date'] = parse_date(line2[21:27], is_dob=False)

    return user_info


def extract_date_of_issue(full_text, dob, expiry_date):
    date_strings = re.findall(r'\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}', full_text)
    cleaned_dates = []
    for date_str in date_strings:
        try:
            date_str_cleaned = re.sub(r'\s+', '', date_str).replace("/", "/ ").strip()
            components = date_str_cleaned.split('/')
            
            if len(components) != 3:
                continue
            
            day = components[0].strip().zfill(2)
            month = components[1].strip().zfill(2)
            year = components[2].strip()
            
            if len(year) == 3:
                year = "2" + year
            elif len(year) == 2:
                current_year = datetime.datetime.now().year
                century = str(current_year)[:2]
                year = f"{century}{year}"
            
            date_str_cleaned = f"{day}/{month}/{year}"
            
            if re.match(r'\d{2}/\d{2}/\d{4}', date_str_cleaned):
                cleaned_dates.append(date_str_cleaned)
        except ValueError:
            continue
    
    dob_date = parser.parse(dob, dayfirst=True).date()
    expiry_date = parser.parse(expiry_date, dayfirst=True).date()
    
    for date_str in cleaned_dates:
        try:
            date = parser.parse(date_str, dayfirst=True).date()
            if date != dob_date and date != expiry_date:
                return date_str
        except ValueError:
            continue
    
    return None

def get_data(img_name):
    user_info = {}
    new_im_path = generate_timestamp_filename()
    im_path = img_name

    try:
        mrz = read_mrz(im_path, save_roi=True)

        if mrz:
            mpimg.imsave(new_im_path, mrz.aux['roi'], cmap='gray')
            img = cv2.imread(new_im_path)
            img = cv2.resize(img, (1110, 140))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            allowlist = st.ascii_uppercase + st.digits + '< '
            code = reader.readtext(img, paragraph=False, detail=0, allowlist=allowlist)
            a, b = code[0].upper(), code[1].upper()

            if len(a) < 44:
                a = a + '<' * (44 - len(a))
            if len(b) < 44:
                b = b + '<' * (44 - len(b))

            user_info = parse_mrz_lines(a, b)
            
            passport_number = user_info['passport_number']
            if passport_number[0].isdigit():
                if passport_number[0] == '2':
                    passport_number = 'Z' + passport_number[1:]
                elif passport_number[0] == '5':
                    passport_number = 'S' + passport_number[1:]
                user_info['passport_number'] = passport_number

        else:
            ocr_output = read_and_display_text(im_path)
            mrz_patterns = [item['text'] for item in ocr_output if '<' in item['text']]

            if len(mrz_patterns) >= 2:
                mrz_line1 = mrz_patterns[0].upper()
                mrz_line2 = mrz_patterns[1].upper()
                user_info = parse_mrz_lines(mrz_line1, mrz_line2)
            else:
                return f'Machine cannot read image {img_name}.'
        
        full_extracted_text = extract_text_from_image(im_path)
        preprocessed_text = preprocess_text(full_extracted_text)
        places_info = extract_cities_and_states(preprocessed_text)
        '''
        print("Full extracted text:", full_extracted_text)
        print("Preprocessed text:", preprocessed_text)
        print("Places info:", places_info)
        '''
        user_info['place_of_birth'] = places_info["place_of_birth"] or "Not found"
        user_info['place_of_issue'] = places_info["place_of_issue"] or "Not found"
       
        if 'date_of_birth' in user_info and 'expiration_date' in user_info:
            dob = user_info['date_of_birth']
            expiry_date = user_info['expiration_date']
            date_of_issue = extract_date_of_issue(full_extracted_text, dob, expiry_date)
            if date_of_issue:
                user_info['date_of_issue'] = date_of_issue

    finally:
        if os.path.exists(new_im_path):
            os.remove(new_im_path)
    
    return user_info

def load_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Failed to load image at path: {image_path}")
    return img

def read_and_display_text(image_path):
    img = load_image(image_path)
    result = reader.readtext(img)
    
    min_ratio = 1.2
    confidence_threshold = 0.01
    
    output = []
    for detection in result:
        text = detection[1].lower()
        confidence = detection[2]
        coordinates = detection[0]

        bbox_width = abs(coordinates[0][0] - coordinates[2][0])
        bbox_height = abs(coordinates[0][1] - coordinates[2][1])
        ratio = bbox_width / bbox_height
        
        if ratio < min_ratio:
            continue

        if confidence < confidence_threshold:
            continue

        output.append({
            "text": text,
            "confidence": confidence,
        })
    
    return output

'''
if __name__ == "__main__":
    img_name = 'data/Edwin Group/Vishwanath Arora/VISHWANATH ARORA P1.jpeg'
    try:
        ocr_output = read_and_display_text(img_name)
        print("Text detected by OCR:")
        print(json.dumps(ocr_output, indent=4))

        user_info = get_data(img_name)
        print("User information extracted:")
        print(json.dumps(user_info, indent=4))
    except FileNotFoundError as e:
        print(e)

'''