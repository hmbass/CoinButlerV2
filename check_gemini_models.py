#!/usr/bin/env python3
"""
Google Gemini API 모델 확인 스크립트
사용 가능한 모델 목록을 조회합니다.
"""
import os
import google.generativeai as genai
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def check_available_models():
    """사용 가능한 Gemini 모델 목록 조회"""
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("❌ GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")
        return
    
    try:
        # API 키 설정
        genai.configure(api_key=api_key)
        
        print("🔍 Google Gemini API 모델 목록 조회 중...")
        print("=" * 60)
        
        # 사용 가능한 모델 목록 조회
        models = genai.list_models()
        
        generation_models = []
        for model in models:
            # generateContent를 지원하는 모델만 필터링
            if 'generateContent' in model.supported_generation_methods:
                generation_models.append(model)
        
        if generation_models:
            print(f"✅ generateContent를 지원하는 모델: {len(generation_models)}개")
            print("-" * 60)
            
            for i, model in enumerate(generation_models, 1):
                print(f"{i:2d}. {model.name}")
                print(f"    설명: {model.display_name}")
                print(f"    버전: {model.version}")
                print(f"    지원 메서드: {', '.join(model.supported_generation_methods)}")
                if hasattr(model, 'input_token_limit'):
                    print(f"    토큰 제한: {model.input_token_limit:,}")
                print()
        else:
            print("❌ generateContent를 지원하는 모델을 찾을 수 없습니다.")
        
        print("=" * 60)
        
        # 추천 모델 테스트
        recommended_models = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro',
            'models/gemini-pro'
        ]
        
        print("🧪 추천 모델 테스트 중...")
        
        for model_name in recommended_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Hello")
                print(f"✅ {model_name}: 정상 작동")
            except Exception as e:
                print(f"❌ {model_name}: {str(e)[:100]}...")
        
        print("\n💡 권장사항:")
        print("- gemini-1.5-flash: 빠르고 비용 효율적 (일반 용도)")
        print("- gemini-1.5-pro: 더 정확하지만 느림 (복잡한 분석)")
        
    except Exception as e:
        print(f"❌ API 호출 실패: {e}")
        print("\n🔧 해결 방법:")
        print("1. GEMINI_API_KEY가 올바른지 확인")
        print("2. https://aistudio.google.com에서 새 API 키 발급")
        print("3. API 키에 충분한 할당량이 있는지 확인")

if __name__ == "__main__":
    check_available_models()
