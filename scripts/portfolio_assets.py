"""Generate portfolio figures from saved evidence, never fabricated screenshots."""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from marketlab.engine import Engine

OUT = ROOT / 'docs' / 'assets'
OUT.mkdir(parents=True, exist_ok=True)
DATA = json.loads((ROOT / 'docs/demo/research.json').read_text())
INK, MUTED, GREEN, RED, LINE = '#202827', '#64716f', '#146a55', '#ad4b45', '#dce4e1'
COLORS = [MUTED, '#4e7aab', GREEN]
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11, 'text.color':INK,
                     'axes.labelcolor':MUTED, 'xtick.color':MUTED, 'ytick.color':MUTED,
                     'axes.spines.top':False, 'axes.spines.right':False,
                     'axes.edgecolor':LINE, 'figure.facecolor':'white', 'axes.facecolor':'white',
                     'svg.fonttype':'none'})


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', dpi=160, facecolor='white')
    fig.savefig(OUT / f'{name}.svg', facecolor='white')
    plt.close(fig)


def heading(fig, title, subtitle):
    fig.text(.06,.935,title,fontsize=21 if len(title) > 45 else 24,weight='bold',ha='left')
    fig.text(.06,.89,subtitle,fontsize=11,color=MUTED,ha='left')


def research():
    fig, axes = plt.subplots(2,1,figsize=(10,6.25),gridspec_kw={'height_ratios':[2.1,1]},sharex=True)
    fig.subplots_adjust(left=.09,right=.95,top=.78,bottom=.17,hspace=.19)
    heading(fig,'Market-making research','Synthetic demo · strict trade-through fills · final held-out sessions')
    for strategy,color,label in zip(['fixed','inventory','signal'],COLORS,['Fixed','Inventory-aware','Signal-aware']):
        result = next(s for s in DATA['strategies'] if s['strategy']==strategy and s['fill']=='through')
        axes[0].plot(np.arange(1,len(result['curve'])+1),[p['equity'] for p in result['curve']],color=color,lw=1.8,label=f"{label}  ${result['pnl']:.4f}")
    signal = next(s for s in DATA['strategies'] if s['strategy']=='signal' and s['fill']=='through')
    axes[1].plot(np.arange(1,len(signal['curve'])+1),[p['inventory'] for p in signal['curve']],color=GREEN,lw=1.2)
    for ax in axes:
        ax.grid(axis='y',color=LINE,alpha=.6)
        ax.axhline(0,color=LINE,lw=1)
        for i in range(1,len(DATA['frames'])):
            if DATA['frames'][i]['session'] != DATA['frames'][i-1]['session']:
                ax.axvline(i+.5,color=LINE,lw=1,ls='--')
    axes[0].set_ylabel('Cumulative P&L (USD)')
    axes[0].legend(frameon=False,loc='lower left',fontsize=10)
    axes[1].set_ylabel('Signal inventory\n(quantity units)')
    axes[1].set_xlabel('Held-out event')
    settings = DATA['settings']
    fig.text(.06,.065,f"Seed {settings['seed']} · {settings['fee_bps']:g} bp maker fee · {settings['latency']} event latency · ±{settings['position_limit']} unit position limit",fontsize=10,color=MUTED)
    fig.text(.06,.03,'Generated from saved results, not a UI screenshot. Session-end marking resets inventory without liquidation costs.',fontsize=8,color=MUTED)
    save(fig,'research-demo')


def sensitivity():
    fig = plt.figure(figsize=(10,6.25))
    heading(fig,'Execution assumptions change the result','Synthetic demo · net simulated P&L (USD) · identical data and settings')
    ax = fig.add_axes([.23,.25,.67,.51])
    strategies, fills = ['fixed','inventory','signal'], ['touch','through','queue']
    values = np.array([[next(s['pnl'] for s in DATA['strategies'] if s['strategy']==strategy and s['fill']==fill) for fill in fills] for strategy in strategies])
    ax.imshow(values,cmap='RdYlGn',vmin=-4,vmax=4,aspect='auto',alpha=.28)
    ax.set_xticks(range(3),['At touch','Trade-through','Queue proxy'])
    ax.set_yticks(range(3),['Fixed','Inventory-aware','Signal-aware'])
    ax.tick_params(axis='both',length=0,pad=16)
    for i in range(3):
        for j in range(3):
            ax.text(j,i,f"{'−' if values[i,j]<0 else '+'}${abs(values[i,j]):.4f}",ha='center',va='center',fontsize=20,weight='medium',color=RED if values[i,j]<0 else GREEN)
    for spine in ax.spines.values():spine.set_visible(False)
    for i in [.5,1.5]:
        ax.axhline(i,color='white',lw=5);ax.axvline(i,color='white',lw=5)
    fig.text(.06,.11,'Eight of nine comparisons lose after fees in this seeded demo.',fontsize=12,weight='medium')
    fig.text(.06,.065,'A positive result under one fill proxy is not evidence of real market profitability.',fontsize=10,color=MUTED)
    fig.text(.06,.03,'Generated from saved results, not a UI screenshot. Queue position and own market impact are unobserved.',fontsize=8,color=MUTED)
    save(fig,'execution-sensitivity')


def box(ax, x, y, width, height, title, body, color=GREEN):
    ax.add_patch(FancyBboxPatch((x,y),width,height,boxstyle='round,pad=0.01,rounding_size=0.014',linewidth=1,edgecolor=LINE,facecolor='#f5f9f6'))
    ax.text(x+.025,y+height-.07,title,fontsize=13,weight='bold',color=color)
    ax.text(x+.025,y+height-.125,body,fontsize=11,linespacing=1.7,va='top',color=INK)


def engine():
    e=Engine()
    stream=[dict(type='order',request_id='a',order_id='alice-ask',participant='alice',side='sell',price=10001,quantity=5),
            dict(type='order',request_id='b',order_id='bob-ask',participant='bob',side='sell',price=10001,quantity=4),
            dict(type='order',request_id='c',order_id='carol-bid',participant='carol',side='buy',price=10001,quantity=7),
            dict(type='order',request_id='d',order_id='dave-ioc',participant='dave',side='buy',price=10000,quantity=3,tif='IOC')]
    responses=[e.execute(c) for c in stream]
    state=e.state()
    assert [(t['maker'],t['quantity']) for t in state['trades']]==[('alice-ask',5),('bob-ask',2)]
    assert state['asks']==[dict(price=10001,quantity=2)]
    assert responses[-1]['cancelled']==3
    fig=plt.figure(figsize=(10,6.25));ax=fig.add_axes([.06,.1,.88,.7]);ax.axis('off')
    heading(fig,'Price-time matching, step by step','Trace generated by the actual matching engine · integer ticks and quantity units')
    box(ax,.01,.52,.43,.39,'Resting asks at 10,001 ticks','Alice · 5 units · first arrival\nBob · 4 units · second arrival')
    box(ax,.55,.52,.43,.39,'Incoming buy at 10,001 ticks','Carol · 7 units\nMatches the earliest order first')
    box(ax,.01,.06,.43,.35,'Two executions','Alice sells 5 units to Carol\nBob sells 2 units to Carol')
    box(ax,.55,.06,.43,.35,'Resulting book','Bob · 2 sell units remain\nDave IOC buy at 10,000: 3 cancelled')
    fig.text(.06,.055,'Resting-price execution · partial fills · IOC cancellation · quantity conserved',fontsize=10,color=MUTED)
    fig.text(.06,.025,'Generated engine trace, not a UI screenshot. Participant names are fictional.',fontsize=8,color=MUTED)
    save(fig,'matching-engine-demo')


def cover():
    fig=plt.figure(figsize=(8,4));ax=fig.add_axes([0,0,1,1]);ax.axis('off')
    fig.text(.075,.79,'MarketLab',fontsize=40,weight='bold',color=INK)
    fig.text(.075,.66,'Market-making research & exchange simulation',fontsize=15,color=MUTED)
    ax.plot([.075,.925],[.53,.53],color=LINE,lw=1,transform=ax.transAxes)
    for x,value,label in [(.075,str(len(DATA['audit']['sessions'])),'synthetic sessions'),(.37,str(len(DATA['predictions'])),'prediction models'),(.665,str(len(DATA['strategies'])),'execution comparisons')]:
        fig.text(x,.36,value,fontsize=29,color=GREEN,weight='medium')
        fig.text(x,.26,label,fontsize=11,color=MUTED)
    fig.text(.075,.10,'Python · scikit-learn · deterministic matching · local dashboard',fontsize=10,color=MUTED)
    save(fig,'portfolio-cover')


if __name__=='__main__':
    cover();research();sensitivity();engine()
    print('Generated 4 PNG images and 4 editable SVG images in docs/assets/.')
