# WarAnt 👑🐜

**WarAnt**은 OGame에서 영감을 받은, 여왕개미가 주인공인 멀티플레이어 웹 전략 게임입니다. 콜로니를 키우고, 야생에서 사냥하고, 경쟁 둥지를 약탈하고, **동맹과 전쟁**을 통해 다른 플레이어와 함께 — 그리고 대결하며 — 제국을 성장시키세요.

[English README](README.md)

## 특징

- **실시간 콜로니 경제** — 먹이와 물이 시간에 따라 축적됩니다(OGame 스타일). 저장고 한도로 상한이 있습니다.
- **행동 에너지** — 업그레이드·연구·진군에는 에너지(최대 100)가 소모되며 시간이 지나면 회복됩니다.
- **현실적인 건설 시간** — 초반 업그레이드는 수십 초, 고단계는 수 시간~수 일입니다.
- **육아방** — 일개미·병정·정찰·비행개미·대형병정·함정턱·산개미를 부화시킵니다.
- **세계 지도(100×100)** — 공격, 정찰, 야생 사냥, 자원 이송, 둥지 간 주둔을 보낼 수 있습니다.
- **전투** — 유닛 스탯·연구 보너스·가시문 방어·터널망 은닉·신규 보호가 적용된 라운드제 전투.
- **동맹 & 전쟁** — 동맹을 창설하고 72시간 전쟁을 선포하세요. 교전 중 공격력 +25%, 격추 전과 점수화.
- **랭킹** — 플레이어/동맹별 콜로니 점수로 경쟁합니다.
- **픽셀아트 UI** — 손으로 만든 픽셀 스프라이트와 모바일 퍼스트 하단 네비게이션.

## 기술 스택

| 계층      | 선택                                        |
| --------- | ------------------------------------------- |
| 풀스택    | [Reflex](https://reflex.dev) (Python → React) |
| 데이터베이스 | SQLModel / SQLAlchemy (SQLite 기본, PostgreSQL 선택) |
| 의존성    | [uv](https://docs.astral.sh/uv/)             |
| 배포      | Docker / docker compose                      |
| 에셋      | 생성형 픽셀아트 SVG (`scripts/gen_sprites.py`) |

## 빠른 시작 (로컬 개발)

Python 3.12와 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
uv sync                                 # 의존성 설치
uv run python scripts/gen_sprites.py   # 픽셀아트 재생성 → assets/img/
uv run reflex init                      # 프론트엔드 1회 부트스트랩
uv run reflex run                       # http://localhost:3000
```

테스트:

```bash
uv run pytest
```

## Docker 배포

```bash
docker compose up --build
```

게임은 **http://localhost:8000** 에서 실행됩니다. 데이터는 `warant_data` 볼륨(`/data/warant.db`)에 저장됩니다. 세션 서명용 `WARANT_SECRET` 환경변수를 설정하고, 필요 시 `WARANT_DATABASE_URL`을 PostgreSQL로 변경하세요(`docker-compose.yml` 참고).

## 플레이 방법

1. **회원가입** — 여왕 이름을 정하면 첫 둥지가 빈 좌표에 세워집니다.
2. **성장** — 버섯 농장(먹이), 이슬 수집기(물), 양광실(에너지 회복), 저장고(한도)를 올리세요.
3. **부화** — 육아방이 자원을 실시간으로 유닛으로 바꿉니다.
4. **정찰 & 사냥** — 정찰개미로 이웃을 염탐하고, 야생 칸에 사냥대를 보내 추가 자원을 모으세요(깊은 야생일수록 위험!).
5. **약탈** — 적 둥지를 공격해 저장 자원을 털어갑니다(터널망이 일부를 숨깁니다).
6. **동맹** — 동맹에 가입하거나 창설하세요. 리더는 전쟁을 선포할 수 있습니다.
7. **랭킹 정복** — 건물·유닛·연구가 모두 콜로니 점수가 됩니다.

### 자원

| 아이콘 | 자원 | 용도 |
| ------ | ---- | ---- |
| 🍒 | **먹이** | 건물, 유닛, 연구 |
| 💧 | **물** | 건물, 유닛, 연구 |
| ⚡ | **행동 에너지** | 업그레이드·생산·진군에 소모되며 시간이 지나면 회복(양광실이 가속) |

## 프로젝트 구조

```
warant/
├── rxconfig.py            # Reflex 설정
├── pyproject.toml         # uv 의존성 관리
├── Dockerfile             # 운영 이미지(프론트엔드 사전 빌드)
├── docker-compose.yml
├── scripts/gen_sprites.py # 픽셀아트 SVG 생성기 -> assets/img/
├── tests/                 # 엔진 단위 테스트 (pytest)
└── warant/
    ├── warant.py          # 앱 연결, 라우트, 백그라운드 티커
    ├── gamedata.py        # 밸런스: 건물/유닛/연구/공식
    ├── models.py          # SQLModel 테이블
    ├── engine.py          # 자원 틱, 대기열, 진군, 전투
    ├── db.py              # 엔진/세션 팩토리 (SQLite/Postgres)
    ├── auth_state.py      # 회원가입/로그인 (bcrypt + 서명 쿠키)
    ├── components/layout.py  # 모바일 퍼스트 셸(상단 바, 하단 내비)
    └── pages/             # 콜로니/건설/군세/연구/지도/보고서/동맹/랭킹/더보기
```

## 에이전트 안내

이 저장소에서 작업하는 AI 에이전트는 먼저 [`AGENTS.md`](AGENTS.md)를 읽어주세요.

---

MIT License — see [LICENSE](LICENSE).
