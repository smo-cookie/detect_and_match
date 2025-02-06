import os
import zipfile
from tempfile import TemporaryDirectory
from lxml import etree
import re
import openai
import json

# 🔑 OpenAI API 키 설정 (사용자가 직접 입력해야 함)
client = openai.Client(api_key="") 

# 주민등록번호 마스킹
def mask_resident_number(text):
    pattern = r"\b\d{6}-\d{7}\b|\b\d{13}\b"
    return re.sub(pattern, "******-*******", text)

# 전화번호 마스킹
def mask_phone_number(text):
    pattern = r"\b010-\d{4}-\d{4}\b"
    return re.sub(pattern, "010-****-****", text)

# 생년월일 마스킹
def mask_birth_date(text):
    pattern = r"\b\d{4}[-/]\d{2}[-/]\d{2}\b"
    return re.sub(pattern, "****-**-**", text)

# 계좌번호 마스킹
def mask_account_number(text):
    pattern = r"\b\d{2,4}-\d{2,4}-\d{2,4}\b"
    return re.sub(pattern, "****-****-****", text)

# 여권번호 마스킹
def mask_passport_number(text):
    pattern = r"\b[A-Z]{1}\d{8}\b"
    return re.sub(pattern, "********", text)

# ✅ 이메일 마스킹 (도메인은 유지)
def mask_email(text):
    pattern = r"\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b"
    return re.sub(pattern, lambda m: "******@" + m.group(0).split("@")[1], text)

# ✅ 신용카드 번호 마스킹
def mask_card_number(text):
    pattern = r"\b\d{4}-\d{4}-\d{4}-\d{4}\b"
    return re.sub(pattern, "****-****-****-****", text)

# ✅ ChatGPT API를 활용한 이름 및 주소 탐지
def detect_pii_with_chatgpt(content):
    """ChatGPT API를 사용하여 이름 및 주소 탐지"""
    prompt = f"""
    다음 텍스트에서 개인정보(이름 및 주소)를 탐지해주세요:
    - 이름은 2~4글자의 한국어 성명일 가능성이 높은 단어입니다.
    - 주소는 "서울시 강남구 역삼동"과 같은 형태일 가능성이 높습니다.
    반환 형식(JSON):
    {{
        "이름": ["홍길동", "김철수"],
        "주소": ["서울시 강남구 역삼동"]
    }}
    텍스트:
    {content}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature = 0
    )

    chatgpt_response = response.choices[0].message.content
    
    try:
        return json.loads(chatgpt_response)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON from ChatGPT"}
    
# ✅ 전체 마스킹 적용 함수
def apply_masking(content):
    # OpenAI를 이용하여 이름과 주소 탐지
    detected_pii = detect_pii_with_chatgpt(content)
    
    # 정규표현식으로 탐지 가능한 정보 마스킹
    content = mask_resident_number(content)
    content = mask_phone_number(content)
    content = mask_birth_date(content)
    content = mask_account_number(content)
    content = mask_passport_number(content)
    content = mask_email(content)
    content = mask_card_number(content)

    # 탐지된 이름과 주소를 마스킹
    for name in detected_pii.get("이름", []):
        content = content.replace(name, "****")
    for address in detected_pii.get("주소", []):
        content = content.replace(address, "****")

    return content

def process_xml_file(xml_path):
    parser = etree.XMLParser(remove_blank_text=True)
    with open(xml_path, 'rb') as file:
        xml_tree = etree.parse(file, parser)
    
    for element in xml_tree.xpath("//w:t", namespaces={"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}):
        if element.text:
            element.text = apply_masking(element.text)
    
    with open(xml_path, 'wb') as file:
        file.write(etree.tostring(xml_tree, pretty_print=True))

def process_comments_xml(comments_path):
    if os.path.exists(comments_path):
        process_xml_file(comments_path)

def mask_sensitive_data_with_images(file_path):
    with TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        document_xml_path = os.path.join(temp_dir, "word", "document.xml")
        if os.path.exists(document_xml_path):
            process_xml_file(document_xml_path)
        
        comments_xml_path = os.path.join(temp_dir, "word", "comments.xml")
        process_comments_xml(comments_xml_path)
        
        new_file_path = file_path.replace(".docx", "(masked).docx")
        with zipfile.ZipFile(new_file_path, 'w') as zip_out:
            for foldername, subfolders, filenames in os.walk(temp_dir):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zip_out.write(file_path, arcname)

    return new_file_path

if __name__ == "__main__":
    input_file = input("마스킹할 Word 파일 경로를 입력하세요: ").strip()
    
    if not os.path.exists(input_file):
        print("파일이 존재하지 않습니다. 경로를 확인하세요.")
    else:
        masked_file = mask_sensitive_data_with_images(input_file)
        print(f"마스킹된 파일이 저장되었습니다: {masked_file}")
