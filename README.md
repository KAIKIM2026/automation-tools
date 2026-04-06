# Slideshow Studio

사진 폴더를 세로형 슬라이드쇼 영상으로 변환하는 Windows용 도구입니다.

## 기능

- 폴더 안의 사진을 시간순으로 정렬해 MP4 영상으로 변환
- 사진당 표시 시간 설정
- 배경색 설정
- 그림자 on/off, blur, distance, opacity 조절
- 출력 형식: `MP4 / H.264`

## 일반 사용자용 사용 방법

가장 쉬운 방법은 GitHub의 `Releases`에서 설치 파일이나 압축 파일을 내려받아 실행하는 것입니다.

1. GitHub 저장소 상단의 `Releases`로 이동합니다.
2. 최신 버전의 `Assets`에서 설치 파일 또는 포터블 압축 파일을 다운로드합니다.
3. 설치 후 `Slideshow Studio`를 실행합니다.
4. 사진 폴더를 선택하고 옵션을 조절한 뒤 `Make Video`를 누릅니다.

출력 영상은 선택한 사진 폴더 안에 `폴더이름_slideshow.mp4` 형식으로 저장됩니다.

## 소스코드로 실행하기

### 1. 저장소 받기

```bat
git clone https://github.com/KAIKIM2026/automation-tools.git
cd automation-tools
```

### 2. Python 버전 실행

`ffmpeg-8.1-essentials_build/bin/ffmpeg.exe`가 프로젝트 루트에 있어야 합니다.

```bat
python slideshow_maker.py
```

### 3. Electron 버전 실행

```bat
cd slideshow-studio
npm install
npm start
```

## 빌드 방법

### Electron 앱 배포 파일 만들기

프로젝트 루트에 `ffmpeg-8.1-essentials_build/bin/ffmpeg.exe`가 있어야 하고, Python과 PyInstaller가 설치되어 있어야 합니다.

```bat
cd slideshow-studio
npm install
npm run dist:win
```

빌드가 끝나면 배포 파일은 `slideshow-studio/dist` 아래에 생성됩니다.

## GitHub Releases 업로드

배포 파일은 저장소 파일 목록에 직접 넣기보다 `Releases`에 올리는 것을 권장합니다.

1. GitHub 저장소 메인 페이지로 이동합니다.
2. 오른쪽의 `Releases` 또는 상단의 `Create a new release`를 누릅니다.
3. 태그를 만들고 제목을 입력합니다.
4. `Attach binaries` 또는 파일 업로드 영역에 설치 파일과 ZIP을 올립니다.
5. `Publish release`를 누릅니다.

권장 업로드 대상:

- 설치 파일 `.exe`
- 포터블 `.zip`

## 개발 메모

- 앱 표시 이름은 `Slideshow Studio`입니다.
- Electron 소스는 `slideshow-studio` 폴더에 있습니다.
- Python 백엔드는 `slideshow-studio/src/python/slideshow_backend.py`에 있습니다.
