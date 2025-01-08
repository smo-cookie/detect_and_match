import re
import json
import openai
from pymongo import MongoClient
from docx import Document
from openpyxl import load_workbook

# api 키 설정
openai.api_key = ""

# MongoDB 설정
client = MongoClient("") # 연결해야함함

db = client["personal_info_db"]  # 유저정보
collection = db["detected_info"] # 저장할 정보 / 컬렉션션

# 정규표현식
patterns = {
    "주민등록번호": r"\\b\\d{6}-\\d{7}\\b",
    "주소": r"\\b[가-힣]+시 [가-힣]+구 [가-힣]+동\\b",
    "연락처": r"\\b010-\\d{4}-\\d{4}\\b",
    "생년월일": r"\\b\\d{4}[-/]\\d{2}[-/]\\d{2}\\b",
    "계좌번호": r"\\b\\d{2,4}-\\d{2,4}-\\d{2,4}\\b",
    "여권번호": r"\\b[A-Z]{1}\\d{8}\\b",
    "이메일": r"\\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\\.)+[A-Za-z]{2,}\\b",
    "카드번호": r"\\b\\d{4}-\\d{4}-\\d{4}-\\d{4}\\b",
    "성명": r"\\b[가-힣]{2,3,4}\\b"
}

# word
def extract_text_from_word(file_path):
    document = Document(file_path)
    return "\\n".join([paragraph.text for paragraph in document.paragraphs])

# excel
def extract_text_from_excel(file_path):
    workbook = load_workbook(file_path)
    text = ""
    for sheet in workbook.sheetnames:
        worksheet = workbook[sheet]
        for row in worksheet.iter_rows(values_only=True):
            text += " ".join([str(cell) if cell else "" for cell in row]) + "\\n"
    return text

# 정규표현식 -> 탐지
def detect_pii_with_regex(content):
    results = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, content)
        if matches:
            if key == "연락처":
                matches = [re.sub(r"\\d{4}-(\\d{4})", "xxxx-\\1", m) for m in matches]
            elif key in ["주민등록번호", "생년월일", "계좌번호", "여권번호", "카드번호"]:
                matches = ["전체 마스킹"] * len(matches)
            elif key == "이메일":
                matches = [re.sub(r"^[^@]+", "******", m) for m in matches]
            elif key == "성명":
                matches = [m[0] + "xx" for m in matches]
            elif key == "주소":
                matches = [re.sub(r"([가-힣]+시 [가-힣]+구 [가-힣]+동)", "**시 **구 **동", m) for m in matches]
            results[key] = matches
    return results

# api 프롬프트 -> 추가정보 요청, 개인정보 모두 포함해서 탐지
def detect_sensitive_info_with_chatgpt(content, additional_info):
    prompt = f\"\"\"\n    아래 텍스트에서 개인정보 및 사용자가 추가적으로 요청한 정보를 찾아주세요:\n    추가 요청 정보: {additional_info}\n    텍스트:\n    {content}\n    \"\"\"\n    response = openai.ChatCompletion.create(\n        model=\"gpt-4\",\n        messages=[{\"role\": \"user\", \"content\": prompt}]\n    )\n    try:\n        return json.loads(response['choices'][0]['message']['content'])\n    except json.JSONDecodeError:\n        return {\"error\": \"Invalid JSON from ChatGPT\"}\n

# db 저장
def save_to_mongodb(file_name, regex_results, chatgpt_results):
    document = {
        "file_name": file_name,   # 파일명
        "regex_results": regex_results, # 정규표현식 결과
        "chatgpt_results": chatgpt_results   # 챗 지피티 결과
    }
    collection.insert_one(document)


def main(file_path, file_type, additional_info):
    if file_type == "word":
        content = extract_text_from_word(file_path)
    elif file_type == "excel":
        content = extract_text_from_excel(file_path)
    else:
        print("지원하지 않는 파일 형식입니다.")
        return

    # 개인정보 탐지
    regex_results = detect_pii_with_regex(content)
    chatgpt_results = detect_sensitive_info_with_chatgpt(content, additional_info)

    # db 저장
    save_to_mongodb(file_path, regex_results, chatgpt_results)

    # 디버깅 용 결과출력
    print(json.dumps({"regex_results": regex_results, "chatgpt_results": chatgpt_results}, ensure_ascii=False, indent=4))

if __name__ == "__main__":
    import sys
    file_path = sys.argv[1]  # 파일 경로
    file_type = sys.argv[2]  # 파일 타입 -> word인지 excel인지 판단
    additional_info = sys.argv[3]  # 추가 탐지 요청 정보 -> gui 구성에 따라 변경경
    main(file_path, file_type, additional_info)
