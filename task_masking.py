import os
import zipfile
from tempfile import TemporaryDirectory
from lxml import etree
import re
import openai
import json

# 🔑 OpenAI API 키 설정
client = openai.Client(api_key="")  # 🔥 실제 API 키 입력 필요

# ✅ 개인정보 마스킹 함수 (전화번호, 주민등록번호, 이메일 등)
def mask_resident_number(text):
    pattern = r"\b\d{6}-\d{7}\b|\b\d{13}\b"
    return re.sub(pattern, "******-*******", text)

def mask_phone_number(text):
    pattern = r"\b010-\d{4}-\d{4}\b"
    return re.sub(pattern, "010-****-****", text)

def mask_birth_date(text):
    pattern = r"\b\d{4}[-/]\d{2}[-/]\d{2}\b"
    return re.sub(pattern, "****-**-**", text)

def mask_account_number(text):
    pattern = r"\b\d{2,4}-\d{2,4}-\d{2,4}\b"
    return re.sub(pattern, "****-****-****", text)

def mask_passport_number(text):
    pattern = r"\b[A-Z]{1}\d{8}\b"
    return re.sub(pattern, "********", text)

def mask_email(text):
    pattern = r"\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b"
    return re.sub(pattern, lambda m: "******@" + m.group(0).split("@")[1], text)

def mask_card_number(text):
    pattern = r"\b\d{4}-\d{4}-\d{4}-\d{4}\b"
    return re.sub(pattern, "****-****-****-****", text)

# ✅ ChatGPT API를 활용한 개인정보 탐지 (additional_info 추가)
def detect_pii_with_chatgpt(content, additional_info=""):
    """ChatGPT API를 사용하여 추가 탐지"""
    prompt = f"""
    다음 텍스트에서 개인정보와 추가 요청된 정보를 탐지해주세요:
    - 개인정보에는 성명, 주소, 연락처, 이메일, 주민등록번호, 계좌번호 등이 포함됩니다.
    - 추가 요청 정보: {additional_info if additional_info else "없음"}
    반환 형식(JSON):
    {{
        "이름": ["홍길동", "김철수"],
        "주소": ["서울시 강남구 역삼동"],
        "개인정보": {{
            "연락처": ["01012345678"],
            "이메일": ["example@domain.com"],
            "주민등록번호": ["9901011234567"],
            "계좌번호": ["1234-5678-9012"],
            "카드번호": ["1234-5678-9012-3456"]
            "생년월일" : ["99.01.01","990101"]
        }},
        "추가 탐지 정보": {{
            "추가 요청 정보": ["Project Alpha"]
        }}
    }}
    텍스트:
    {content}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    chatgpt_response = response.choices[0].message.content

    try:
        return json.loads(chatgpt_response)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON from ChatGPT"}

# ✅ 전체 마스킹 적용 함수 (additional_info 포함)
# ✅ 전체 마스킹 적용 함수 (정규표현식 + ChatGPT 탐지 결과 포함)
# ✅ 전체 마스킹 적용 함수 (정규표현식 + ChatGPT 탐지 결과 포함)
def apply_masking(content, additional_info=""):
    """
    전체 마스킹 처리 (정규표현식 + ChatGPT 탐지 결과)
    :param content: 원본 텍스트
    :param additional_info: 추가 탐지할 정보 (회사명, 프로젝트명 등)
    :return: 개인정보가 마스킹된 텍스트
    """

    # 🔍 1️⃣ OpenAI ChatGPT를 이용하여 추가 개인정보 탐지
    detected_pii = detect_pii_with_chatgpt(content, additional_info)

    # 🔍 2️⃣ 정규표현식으로 탐지 가능한 정보 마스킹 (탐지된 데이터를 리스트로 저장)
    pii_list = []

    # ✅ 정규표현식으로 탐지된 데이터 저장
    pii_list.append(mask_resident_number(content))    # 주민등록번호
    pii_list.append(mask_phone_number(content))      # 전화번호
    pii_list.append(mask_birth_date(content))        # 생년월일
    pii_list.append(mask_account_number(content))    # 계좌번호
    pii_list.append(mask_passport_number(content))   # 여권번호
    pii_list.append(mask_email(content))             # 이메일
    pii_list.append(mask_card_number(content))       # 카드번호

    # ✅ ChatGPT 탐지된 개인정보 추가 (이름, 주소, 연락처, 이메일 등)
    pii_list.extend(detected_pii.get("이름", []))
    pii_list.extend(detected_pii.get("주소", []))

    # ✅ ChatGPT 탐지된 추가 개인정보 (전화번호, 이메일, 주민등록번호 등)
    for key, values in detected_pii.get("개인정보", {}).items():
        pii_list.extend(values)

    # ✅ 추가 탐지 정보 (회사명, 프로젝트명 등) 마스킹 추가
    for key, values in detected_pii.get("추가 탐지 정보", {}).items():
        pii_list.extend(values)

    # 🔥 3️⃣ 탐지된 모든 개인정보를 `****`로 마스킹 처리
    for pii in pii_list:
        if isinstance(pii, str):  # 문자열인 경우만 처리
            cleaned_pii = pii.strip()  # 공백 제거
            if cleaned_pii in content:  # 원본 텍스트에 포함된 경우에만 마스킹
                content = content.replace(cleaned_pii, "****")

    return content



def process_xml_file(xml_path, additional_info=""):
    parser = etree.XMLParser(remove_blank_text=True)
    with open(xml_path, 'rb') as file:
        xml_tree = etree.parse(file, parser)

    for element in xml_tree.xpath("//w:t", namespaces={"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}):
        if element.text:
            element.text = apply_masking(element.text, additional_info)

    with open(xml_path, 'wb') as file:
        file.write(etree.tostring(xml_tree, pretty_print=True))

def process_comments_xml(comments_path, additional_info=""):
    if os.path.exists(comments_path):
        process_xml_file(comments_path, additional_info)

def mask_sensitive_data_with_images(file_path, additional_info=""):
    with TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        document_xml_path = os.path.join(temp_dir, "word", "document.xml")
        if os.path.exists(document_xml_path):
            process_xml_file(document_xml_path, additional_info)

        comments_xml_path = os.path.join(temp_dir, "word", "comments.xml")
        process_comments_xml(comments_xml_path, additional_info)

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
    additional_info = input("추가적으로 탐지할 정보를 입력하세요 (예: 회사 프로젝트명, 내부 코드 등, 없으면 엔터): ").strip()

    if not os.path.exists(input_file):
        print("파일이 존재하지 않습니다. 경로를 확인하세요.")
    else:
        masked_file = mask_sensitive_data_with_images(input_file, additional_info)
        print(f"마스킹된 파일이 저장되었습니다: {masked_file}")
