import re
from indian_cities.dj_city import cities
from fuzzywuzzy import fuzz
import cv2
import easyocr
from nltk import ngrams

def extract_text_from_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error loading image {image_path}")
        return ""
    
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    reader = easyocr.Reader(['en'])
    result = reader.readtext(gray_img)
    extracted_text = ' '.join([entry[1] for entry in result])
    return extracted_text

def preprocess_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s<]|_', ' ', text)  
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_ngrams(text, n):
    return [''.join(gram) for gram in ngrams(text, n)]

def partial_city_match(word, city_name):
    word = word.lower()
    city_name = city_name.lower()
    
    if word in city_name:
        return True
    
    if len(word) >= 4 and fuzz.partial_ratio(word, city_name) >= 90:
        return True
    
    return False

def is_excluded_city(city_name):
    excluded_cities = ["anand"] 
    return city_name.lower() in excluded_cities    

def calculate_match_score(word, city_name, nearby_words):
    score = 0
    
    if partial_city_match(word, city_name):
        score += 80  # High score for partial matches
    
    if word.lower() in city_name.lower():
        score += 20
    
    word_grams = set(get_ngrams(word, 3))
    city_grams = set(get_ngrams(city_name, 3))
    common_grams = word_grams.intersection(city_grams)
    score += len(common_grams) * 5
    
    context_keywords = ["birth", "issue", "issued", "place", "of", "date"]
    if any(keyword in nearby_words.lower() for keyword in context_keywords):
        score += 25
    
    return score

def find_best_match(word, start_index, end_index, words):
    nearby_words = ' '.join(words[max(0, start_index-12):min(len(words), end_index+15)])
    best_match = {"city": None, "state": None, "score": 0, "position": start_index}
    
    for state, city_list in cities:
        for city_tuple in city_list:
            city_name = city_tuple[0].lower()
            if not is_excluded_city(city_name) and partial_city_match(word, city_name):
                score = calculate_match_score(word, city_name, nearby_words)
                
                if score > best_match["score"]:
                    best_match = {"city": city_tuple[0], "state": state, "score": score, "position": start_index}
    
    return best_match

def find_exact_match(word, city_list):
    for city_tuple in city_list:
        if word.lower() == city_tuple[0].lower() and not is_excluded_city(city_tuple[0]):
            return city_tuple[0]
    return None

def extract_cities_and_states(text):
    words = text.split()
    detected_cities = []
    detected_states = []
    exact_matches = []
    '''
    print("Debugging: Checking each word for exact city and state match")
    '''
    # Skip the first 20 words
    words_to_check = words[10:]  
    for i, word in enumerate(words_to_check):
        if len(word) < 3:  # Skip short words
            continue
        '''
        print(f"Checking word: '{word}'")
        '''
        exact_match_found = False
        for state, city_list in cities:
            exact_match = find_exact_match(word, city_list)
            if exact_match:
                '''
                print(f"Exact match found: {exact_match}, {state}")
                '''            
                exact_matches.append({"city": exact_match, "state": state, "position": i + 17})  # Adjust position accordingly
                exact_match_found = True
                break
        
        if not exact_match_found:
            start_index = max(0, i - 12)
            end_index = min(len(words), i + 15)
            match = find_best_match(word, start_index, end_index, words)
            if match["score"] > 80:  
                '''
                print(f"Potential partial match found: {match['city']}, {match['state']} (Score: {match['score']})")
                ''' 
                detected_cities.append({"city": match['city'], "state": match['state'], "position": i + 17})  # Adjusting position
        
        for state, city_list in cities:
            state_lower = state.lower()
            if word.lower() == state_lower or (state_lower.endswith(' pradesh') and word.lower() == state_lower.split()[0]):
                '''
                print(f"Potential state match found: {state}")
                '''
                detected_states.append(state)

    exact_matches.sort(key=lambda x: x["position"])
    detected_cities.sort(key=lambda x: x["position"])
    detected_states = list(set(detected_states))  # Remove duplicates
    '''
    print(f"Exact matches: {exact_matches}")
    print(f"Detected cities: {detected_cities}")
    print(f"Detected states: {detected_states}")
    '''
    places_info = {
        "place_of_birth": None,
        "place_of_issue": None
    }
    
    # Update logic to ensure exact city matches use their actual states
    if len(exact_matches) >= 2:
        places_info["place_of_birth"] = format_place(exact_matches[0], [])
        places_info["place_of_issue"] = format_place(exact_matches[1], [])
    elif len(exact_matches) == 1:
        places_info["place_of_issue"] = format_place(exact_matches[0], [])
        if len(detected_states) > 0:
            places_info["place_of_birth"] = detected_states[0]
    elif len(detected_cities) >= 1:
        places_info["place_of_issue"] = format_place(detected_cities[0], detected_states)
        if len(detected_states) > 0:
            places_info["place_of_birth"] = detected_states[0]
    
    return places_info


def format_place(city_info, detected_states):
    if detected_states:
        return f"{city_info['city']}, {detected_states[0]}"
    else:
        return f"{city_info['city']}, {city_info['state']}"

def extract_dates(text):
    date_pattern = r"\b\d{2}/\d{2}/\d{4}\b"
    return re.findall(date_pattern, text)

def process_image(image_path):
    extracted_text = extract_text_from_image(image_path)
    preprocessed_text = preprocess_text(extracted_text)
    
    places_info = extract_cities_and_states(preprocessed_text)

    return extracted_text, preprocessed_text, places_info

'''
if __name__ == "__main__":
    image_path =  
    extracted_text, preprocessed_text, places_info = process_image(image_path)
    
    print("Original Extracted Text:")
    print(extracted_text)
    print("\nPreprocessed Text:")
    print(preprocessed_text)
    print("\nPlace of Birth:", places_info["place_of_birth"] or "Not found")
    print("Place of Issue:", places_info["place_of_issue"] or "Not found")
'''