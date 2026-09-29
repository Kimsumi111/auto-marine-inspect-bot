"""Render the paper's simulator architecture from the verified implementation."""
from pathlib import Path
import math
from html import escape
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / 'output' / 'figures'
OUT.mkdir(parents=True, exist_ok=True)
S = 2.2
canvas = Image.new('RGB',(3740,2464),'white')
draw = ImageDraw.Draw(canvas)
svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1700" height="1120" viewBox="0 0 1700 1120">',
       '<rect width="1700" height="1120" fill="white"/>']
ink, blue, orange = '#263442', '#27628D', '#A55C20'

def text(x, y, value, size=13, weight=False, color=ink, ha='center'):
    fs=size*1.4
    font=ImageFont.truetype(r'C:\Windows\Fonts\malgunbd.ttf' if weight else r'C:\Windows\Fonts\malgun.ttf',round(fs*S))
    lines=value.split('\n')
    for i,t in enumerate(lines):
        yy=y+(i-(len(lines)-1)/2)*fs*1.55
        draw.text((x*S,yy*S),t,font=font,fill=color,anchor='mm')
        svg.append(f'<text x="{x}" y="{yy}" font-family="Malgun Gothic, sans-serif" font-size="{fs}" font-weight="{700 if weight else 400}" text-anchor="middle" dominant-baseline="central" fill="{color}">{escape(t)}</text>')

def panel(x,y,w,h,fill,edge,r=8):
    draw.rounded_rectangle((x*S,y*S,(x+w)*S,(y+h)*S),radius=r*S,fill=fill,outline=edge,width=3)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{edge}" stroke-width="1.3"/>')

def box(x, y, w, h, title, detail='', fill='#FFFFFF', edge=ink):
    panel(x,y,w,h,fill,edge)
    text(x+w/2,y+(h/2 if not detail else 28),title,15,True)
    if detail:
        text(x+w/2,y+28+(h-28)/2,detail,12)

def line(points, color=ink, dashed=False, arrow=True):
    for a,b in zip(points,points[1:]):
        length=math.dist(a,b)
        if dashed:
            for k in range(0,int(length),12):
                p=[(a[j]+(b[j]-a[j])*k/length)*S for j in (0,1)]
                q=[(a[j]+(b[j]-a[j])*min(k+7,length)/length)*S for j in (0,1)]
                draw.line([tuple(p),tuple(q)],fill=color,width=3)
        else:
            draw.line([(a[0]*S,a[1]*S),(b[0]*S,b[1]*S)],fill=color,width=3)
    dash=' stroke-dasharray="7 5"' if dashed else ''
    svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="1.5"{dash}/>')
    if arrow:
        a,b=points[-2:]; angle=math.atan2(b[1]-a[1],b[0]-a[0])
        tri=[b,(b[0]-11*math.cos(angle)+5*math.sin(angle),b[1]-11*math.sin(angle)-5*math.cos(angle)),(b[0]-11*math.cos(angle)-5*math.sin(angle),b[1]-11*math.sin(angle)+5*math.cos(angle))]
        draw.polygon([(x*S,y*S) for x,y in tri],fill=color)
        svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in tri)}" fill="{color}"/>')

text(850,30,'Unity 기반 자율 순찰·점검 시뮬레이터 구조',22,True)
panel(30,72,1240,940,'#FAFCFE','#91A3B2',12)
panel(1320,72,350,940,'#FFFCF8','#B9A28E',12)
text(650,100,'운용 · 데모 환경',16,True,color=blue)
text(1495,100,'학습 · 모델 배포',16,True,color=orange)
box(75,132,1150,80,'가상 설비·주행 환경',
    '설비 A·B  /  노란색 주행 경계선  /  바닥 마커·점검 지점  /  보행자 시나리오',fill='#ECF3F8')

centres=[200,500,800,1100]
titles=['전방 RGB 영상','좌·우 가상 ToF','마커 모의 관측','로봇·트랙 상태']
details=['HSV 차선 검출\nYOLOX-S 사람 검출','거리·접근 속도\n충돌 예상 시간(TTC)','씬 좌표·카메라 시야\n6개 노드·경로 그래프','속도·각속도·구동 명령\n트랙 복귀 방향 정보']
for x,t,d in zip(centres,titles,details):
    box(x-125,260,250,112,t,d)
    line([(x,212),(x,260)])
    line([(x,372),(x,400)],arrow=False)
line([(200,400),(1100,400)],arrow=False)
text(650,387,'인식 결과 및 상태 정보',11,color=blue)

titles=['차선·임무 주행','PPO 사람 회피','알고리즘 차선 복귀','ADAS 안전 제어']
details=['차선 중심 추종·코너링\n경로 이동·점검 정지','관측 20차원 × 4시점\n연속 이동·회전 명령','위험 해소 후 재탐색\n차선 정렬·주행 재개','거리·TTC 기반 감속\n근접 위험 시 긴급 정지']
for x,t,d in zip(centres,titles,details):
    box(x-125,462,250,125,t,d,fill='#ECF3F8')
    line([(x,400),(x,462)])
    line([(x,587),(x,645)],arrow=False)
line([(200,645),(1100,645)],arrow=False)
line([(650,645),(650,700)])
box(280,700,740,100,'제어 권한 조정',
    '점검·임무 정지 / ADAS 긴급 정지 → PPO 회피·차선 복귀 → 일반 주행',fill='#DEEAF3')
line([(650,800),(650,848)])
box(280,848,740,100,'로봇 구동 및 물리 시뮬레이션',
    '좌우 바퀴 구동 → 로봇 이동·회전 → 센서 관측 갱신')
line([(280,898),(52,898),(52,172),(75,172)])
text(150,925,'상태 피드백',11)
text(650,983,'점검 지점 정지는 점검 동작을 표현하는 데모이며, 설비 진단 모듈과는 별도 구성',11)

box(1345,132,300,116,'학습용 Unity 환경',
    '보행자 접근·로봇 초기화\n보상·성공·충돌·이탈 판정',fill='#F7EEE4')
line([(1455,248),(1455,305)],color=orange)
line([(1535,305),(1535,248)],color=orange)
text(1495,277,'ML-Agents',10,color=orange)
box(1345,305,300,112,'Python PPO 학습기',
    '관측·행동·보상 교환\n정책 갱신·체크포인트 저장',fill='#F7EEE4')
line([(1495,417),(1495,488)],color=orange)
box(1345,488,300,88,'학습 정책 ONNX','Unity 내 추론에 사용',fill='#F7EEE4')
line([(1345,532),(1295,532),(1295,433),(500,433),(500,462)],color=orange,dashed=True)
text(980,421,'학습 모델 배포',10,color=orange)
line([(1645,361),(1657,361),(1657,750),(1645,750)],color=orange)
box(1345,700,300,100,'W&B 학습 모니터링','보상·성공률·충돌률\n트랙 이탈·행동 지표')
text(1495,890,'학습 시: Python 학습기 연동\n데모 시: 저장 모델 추론',12)
text(850,1053,'실선: 데이터·제어 흐름     점선: 학습된 모델의 배포',12)
text(850,1088,'바닥 마커와 트랙 보정은 시뮬레이터 상태를 이용한 정보이며, 실제 영상 마커 해독과 구분된다.',11)

canvas.save(OUT/'simulator-system-architecture.png',dpi=(220,220))
(OUT/'simulator-system-architecture.svg').write_text('\n'.join(svg)+ '\n</svg>',encoding='utf-8')
canvas.resize((1530,1008)).save(OUT/'simulator-system-architecture-preview.png')
print(OUT)
