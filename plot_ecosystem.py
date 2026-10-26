"""Population renewal, ancestry, and operational genetic-diversity views."""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'.cache/matplotlib'))
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection

from experiment_ecosystem import analyze_results,load_run,validate_run
from plot_traits import export,style

COLORS={'mutating':'#158775','clonal':'#a36aab'}


def save_run_plot(report,path):
    validate_run(report);rows=report['snapshots'];f=Figure(figsize=(13,9),facecolor='#f8fafc');FigureCanvasAgg(f);axes=f.subplots(2,2)
    f.subplots_adjust(left=.09,right=.96,top=.85,bottom=.13,wspace=.3,hspace=.45)
    f.suptitle(f"Continuous ecosystem · seed {report['seed']}",fontsize=21,fontweight='bold')
    time=[r['time'] for r in rows]
    for axis,key,title in zip(axes.flat,('population','births','effective_families','within_family_rms'),
                              ('Living population','Cumulative funded births','Effective founder families','Within-family genetic RMS')):
        axis.plot(time,[r[key] if r[key] is not None else np.nan for r in rows],color=COLORS['mutating'],linewidth=2)
        axis.set(title=title,xlabel='Simulated seconds')
    style(axes.flat);f.text(.07,.045,'No cohort resets or creature immigration. Founder families are genealogical; genetic clusters do not establish species.',fontsize=10,color='#536876');export(f,path)


def build_study_figure(report):
    if report.get('status')!='complete':raise ValueError('Plot only a complete continuous study.')
    analysis=analyze_results(report);f=Figure(figsize=(16,11),facecolor='#f8fafc');FigureCanvasAgg(f);axes=f.subplots(2,3)
    f.subplots_adjust(left=.08,right=.96,top=.82,bottom=.17,wspace=.35,hspace=.55)
    f.suptitle('Continuous evolution in a renewable habitat',fontsize=23,fontweight='bold',y=.97,color='#173344')
    f.text(.5,.92,f"{analysis['independent_seed_groups']} independent seeds · funded births and overlapping lifetimes · {report['protocol']['duration']:g}-second horizon",ha='center',fontsize=12,color='#536876')
    f.text(.5,.875,'Each line is a complete ecosystem. Extinct runs remain zero; genetic pair metrics are undefined after extinction.',ha='center',fontsize=11,color='#536876')
    for row,resource in enumerate(('abundant','scarce')):
        for trial in report['trials']:
            for arm in COLORS:
                record=trial['runs'][resource][arm];points=record['snapshots'];time=[p['time'] for p in points]
                population=[p['population'] for p in points]
                if time[-1]<report['protocol']['duration']:time=time+[report['protocol']['duration']];population=population+[0]
                axes[row,0].plot(time,population,color=COLORS[arm],alpha=.5,linewidth=1)
                axes[row,1].plot([p['time'] for p in points],[len(p['family_counts']) for p in points],color=COLORS[arm],alpha=.5,linewidth=1)
                axes[row,2].plot([p['time'] for p in points],[p['within_family_rms'] if p['within_family_rms'] is not None else np.nan for p in points],color=COLORS[arm],alpha=.5,linewidth=1)
        for col,title in enumerate(('Living population','Surviving founder families','Within-family genetic RMS')):
            axes[row,col].set(title=f'{resource.title()}: {title}',xlabel='Seconds',xlim=(0,report['protocol']['duration']))
            if col!=2:axes[row,col].set_ylim(bottom=0)
    style(axes.flat)
    f.text(.065,.11,'Teal: neural and body mutation. Purple: clonal reproduction, with identical founders and initial habitat within each resource condition.',fontsize=10,color='#536876')
    counts=[]
    for resource in ('abundant','scarce'):
        for arm in COLORS:
            a=analysis['conditions'][resource][arm];counts.append(f"{resource}/{arm}: {a['persisting_runs']}/{a['runs']} renewed populations")
    f.text(.065,.07,'; '.join(counts),fontsize=9,color='#536876')
    f.text(.065,.03,'Renewal requires living descendants, no living founders, depth ≥ 3, and births in the last 120 seconds. A finite horizon does not prove indefinite sustainability.',fontsize=9,color='#536876')
    return f


def save_ancestry_plot(study,path):
    if study.get('status')!='complete':raise ValueError('Plot only a complete study.')
    first=next(t for t in study['trials'] if t['seed']==study['protocol']['seeds'][0]);r=load_run(first['runs']['abundant']['mutating'])
    f=Figure(figsize=(15,10),facecolor='#f8fafc');FigureCanvasAgg(f);axes=f.subplots(2,1)
    f.subplots_adjust(left=.08,right=.96,top=.82,bottom=.15,hspace=.5)
    f.suptitle(f"Ancestry of the predetermined ecosystem · seed {first['seed']}",fontsize=22,y=.97)
    f.text(.5,.915,'Abundant resources with mutation. All births and parent edges are included; ancestry depth is not a synchronized generation.',ha='center',fontsize=11,color='#536876')
    births=r['births'];lookup={b['creature_id']:b for b in births}
    edges=[[(lookup[b['parent_id']]['born_at'],lookup[b['parent_id']]['depth']),(b['born_at'],b['depth'])] for b in births if b['parent_id'] is not None]
    axes[0].add_collection(LineCollection(edges,colors='#b7c8d2',linewidths=.4,alpha=.5))
    axes[0].scatter([b['born_at'] for b in births],[b['depth'] for b in births],c=[b['founder_id'] for b in births],cmap='turbo',s=8,vmin=1,vmax=r['initial_population'])
    axes[0].set(xlim=(-2,study['protocol']['duration']),ylim=(-.5,max(b['depth'] for b in births)+1),title='Every birth and its parent',xlabel='Birth time (seconds)',ylabel='Ancestral depth')
    final=r['snapshots'][-1]['family_counts'];totals={str(k):sum(b['founder_id']==k for b in births) for k in range(1,r['initial_population']+1)}
    selected=sorted(totals,key=lambda k:(-final.get(k,0),-totals[k],int(k)))[:8]
    rows=r['snapshots'];series=[[p['family_counts'].get(k,0) for p in rows] for k in selected]
    series.append([p['population']-sum(p['family_counts'].get(k,0) for k in selected) for p in rows])
    axes[1].stackplot([p['time'] for p in rows],series,labels=[f'Founder {k}' for k in selected]+['Other families'],alpha=.8)
    axes[1].set(title='Largest final families (cumulative size breaks ties); all others pooled',xlabel='Seconds',ylabel='Living descendants')
    axes[1].legend(fontsize=7,ncol=5,frameon=False,loc='upper right');style(axes)
    f.text(.07,.08,'Colors identify genealogical founder families. A family may contain multiple genetic neighborhoods; neither family labels nor threshold clusters establish speciation.',fontsize=9,color='#536876')
    f.text(.07,.035,'Full lifetime reports and numerical genomes retain extinct branches as well as survivors. No demographic rescue or top-fitness cohort replacement is used.',fontsize=10,color='#536876');export(f,path)


def save_world_image(study,path):
    if study.get('status')!='complete':raise ValueError('Render only a complete study.')
    from ecosystem import ContinuousWorld,ContinuousSimulation
    from main import draw_interface,PADDING,HEADER_HEIGHT,FOOTER_HEIGHT
    import pygame
    trial=next(t for t in study['trials'] if t['seed']==study['protocol']['seeds'][0])
    raw=load_run(trial['runs']['abundant']['mutating'])
    world=ContinuousWorld(seed=trial['seed']);simulation=ContinuousSimulation(world,duration=study['protocol']['duration'])
    simulation.update(min(120.,simulation.duration))
    world.sample()
    matching=next((r for r in raw['snapshots'] if r['time']==world.elapsed_time),None)
    if matching is not None and matching!=world.snapshots[-1]:raise ValueError('Arena replay differs from the saved ecosystem.')
    world.selected_creature=next(iter(world.creatures),None)
    os.environ['SDL_VIDEODRIVER']='dummy';pygame.display.init();pygame.font.init()
    try:
        screen=pygame.display.set_mode((world.width+2*PADDING,world.height+HEADER_HEIGHT+FOOTER_HEIGHT))
        fonts={'title':pygame.font.Font(None,38),'small':pygame.font.Font(None,20)};draw_interface(screen,world,fonts,simulation)
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);pygame.image.save(screen,str(path))
    finally:pygame.quit()


def draw_continuous_interface(screen,world,fonts,simulation):
    import pygame
    from main import BACKGROUND,TEXT,MUTED,PADDING,HEADER_HEIGHT,draw_trend
    screen.fill(BACKGROUND);font=fonts['small']
    def label(text,x,y,color=TEXT):screen.blit(font.render(text,True,color),(x,y))
    label('ARTIFICIAL EVOLUTION / STEP 26',40,22,(101,219,181))
    screen.blit(fonts['title'].render('A continuously evolving ecosystem',True,TEXT),(40,43))
    label(f"{len(world.creatures)} ALIVE / {len(world.births)-world.population_size} BIRTHS / {len(world.deaths)} DEATHS",630,25)
    label(f"{world.elapsed_time:.1f}/{simulation.duration:g}s   {simulation.speed}x   Births {'ON' if world.reproduction_enabled else 'OFF'}",630,49,MUTED)
    label(f"Food {len(world.food)}/{world.food_count} / Regrowth {world.regrowth_rate:g}/s / {'EXTINCT' if world.lineage_extinct else 'PAUSED' if world.paused else 'HORIZON' if simulation.finished else 'RUNNING'}",40,82,MUTED)
    world.draw(screen,(PADDING,HEADER_HEIGHT));y=HEADER_HEIGHT+world.height+15
    label('Space Pause / A Births on-off / S Speed / R Restart / F Families / T History / V Senses / Esc Quit',40,y,MUTED)
    c=world.selected_creature
    if c is not None:
        label(f"#{c.creature_id} / Parent {c.parent_id or 'founder'} / Root {c.founder_id} / Depth {c.generation-1} / Age {c.age:.1f}s / Children {c.children}",40,y+24,c.color)
        label(f"Energy {c.energy:.1f}/{c.energy_capacity:.1f} / Born at {c.born_at:.1f}s / Speed {c.speed:.1f} / Size {c.radius} / Sight {c.body.sensory_range:.0f}",40,y+46,MUTED)
    else:label('Click an actor to inspect its parent, founder family, ancestry depth, and inherited traits.',40,y+28,MUTED)
    if not (world.show_history or world.show_fitness):return
    panel=pygame.Rect(90,170,900,475);pygame.draw.rect(screen,BACKGROUND,panel,border_radius=12);pygame.draw.rect(screen,MUTED,panel,1,border_radius=12)
    if world.show_fitness:
        counts={root:sum(c.founder_id==root for c in world.creatures) for root in {c.founder_id for c in world.creatures}}
        label('Living founder families / ancestry labels are not biological species',120,195)
        for i,(root,count) in enumerate(sorted(counts.items(),key=lambda p:(-p[1],p[0]))[:12]):
            label(f"Founder #{root:03d} / Living descendants {count:3d} / Historical births {sum(c.founder_id==root for c in world.registry.values())}",120,235+i*28)
    else:
        rows=world.snapshots;g=[r['time'] for r in rows]
        label('Continuous time / births and deaths overlap / no cohort reset',120,195)
        draw_trend(screen,pygame.Rect(120,270,390,235),'Living population',[([r['population'] for r in rows],(101,219,181))],g,font,label_prefix='t=')
        draw_trend(screen,pygame.Rect(560,270,390,235),'Effective founder families',[([r['effective_families'] for r in rows],(187,155,236))],g,font,label_prefix='t=')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('report',type=Path);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--ancestry-output',type=Path);parser.add_argument('--world-output',type=Path);args=parser.parse_args()
    try:
        r=json.loads(args.report.read_text())
        if r.get('mode')=='continuous':save_run_plot(r,args.output)
        else:
            export(build_study_figure(r),args.output)
            if args.ancestry_output:save_ancestry_plot(r,args.ancestry_output)
            if args.world_output:save_world_image(r,args.world_output)
    except (ValueError,OSError) as error:parser.error(str(error))
    return 0


if __name__=='__main__':raise SystemExit(main())
