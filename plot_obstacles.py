"""Avoidance metrics, corrected comparisons, and the actual held-out geometry."""

import argparse
import copy
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'.cache/matplotlib'))
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
import numpy as np

from compare_creatures import initial_conditions_digest
from experiment_obstacles import CONDITIONS, analyze_results, validate_cohorts
from obstacles import ObstacleWorld

COLORS=('#087f8c','#9861a1','#b97b2d')


def export(figure,path):
    path=Path(path)
    if path.suffix.lower() not in ('.png','.svg','.pdf'):raise ValueError('Use PNG, SVG, or PDF.')
    path.parent.mkdir(parents=True,exist_ok=True)
    try:figure.savefig(path,dpi=160,facecolor=figure.get_facecolor())
    finally:figure.clear()


def style(axes):
    for axis in axes:
        axis.set_facecolor('white');axis.tick_params(labelsize=8,colors='#536876')
        axis.title.set_fontsize(11)
        axis.grid(axis='y',color='#e1e8ee',linewidth=.7);axis.set_axisbelow(True)
        for spine in axis.spines.values():spine.set_color('#cddae3')


def build_study_figure(report):
    if report.get('status')!='complete':raise ValueError('Visualize only a complete obstacle study.')
    a=analyze_results(report);figure=Figure(figsize=(16,11),facecolor='#f8fafc');FigureCanvasAgg(figure)
    axes=figure.subplots(2,3)
    figure.subplots_adjust(left=.075,right=.97,bottom=.17,top=.81,wspace=.36,hspace=.65)
    figure.suptitle('Can evolution improve avoidance while foraging?',fontsize=22,fontweight='bold',y=.97,color='#173344')
    figure.text(.5,.925,f"{a['independent_seed_groups']} independent training seeds · 16–8–2 networks · fixed 60 pixels/s · {report['protocol']['repeats']} matched new layouts per seed",ha='center',fontsize=12,color='#536876')
    figure.text(.5,.88,'Barriers reflect on contact. Impacts and dangerous exposure cost energy and fitness. All cohorts include early deaths.',ha='center',fontsize=11,color='#536876')
    axis=axes[0,0]
    histories=[t['training']['generations'] for t in report['trials']]
    g=np.arange(1,len(histories[0])+1)
    for rows in histories:axis.plot(g,[r['mean_fitness'] for r in rows],color='#9aadb8',alpha=.5,linewidth=1)
    axis.plot(g,np.mean([[r['mean_fitness'] for r in rows] for rows in histories],axis=0),color=COLORS[0],linewidth=2.5,marker='o')
    axis.set(title='Training fitness (new geometry every generation)',xlabel='Generation',ylabel='Penalized fitness')
    for axis,metric,key,title,ylabel in (
        (axes[0,1],'mean_fitness','fitness_gain','Held-out penalized fitness','Age + 10 × meals − risk penalties'),
        (axes[0,2],'mean_food_eaten','food_gain','Held-out food consumption','Meals per creature'),
        (axes[1,0],'collision_rate','collision_change','Barrier collisions per living minute','Collisions / creature-minute'),
        (axes[1,1],'hazard_fraction','hazard_change','Fraction of living time in dangerous regions','Hazard exposure / living time'),
    ):
        for index,condition in enumerate(CONDITIONS):
            values=np.array(a['seed_values'][condition][metric]);axis.bar(index,values.mean(),width=.55,color=COLORS[index],alpha=.65)
            axis.scatter(index+np.linspace(-.12,.12,len(values)),values,color=COLORS[index],s=18,zorder=3)
        axis.set_xticks(range(3),['Evolved','Risk hidden','Founders'],fontsize=9)
        axis.set(ylabel=ylabel);axis.set_title(title,pad=25)
        p=a['primary'][key]
        axis.text(.02,1.02,f"Evolved − founders: {p['conclusion']}; Holm p={p['holm_adjusted_p']:.4g}",transform=axis.transAxes,fontsize=8,color='#536876')
    axis=axes[1,2];effect=a['primary']['risk_sensor_benefit']
    raw=np.array(a['seed_values']['evolved']['mean_fitness'])-a['seed_values']['risk_hidden']['mean_fitness']
    axis.scatter(raw,np.linspace(-.08,.08,len(raw)),color='#9aadb8',s=25)
    lo,hi=effect['difference_ci95'];mean=effect['mean_difference']
    axis.hlines(0,lo,hi,color=COLORS[0],linewidth=3);axis.scatter(mean,0,marker='D',s=60,color=COLORS[0]);axis.axvline(0,color='#98aab6',linestyle='--')
    axis.set(title='Do the eight added risk inputs help?',xlabel='Fitness: evolved intact − same brains risk-hidden',ylim=(-.35,.35),yticks=[])
    axis.text(.5,.83,f"Δ {mean:+.2f}; 95% [{lo:+.2f}, {hi:+.2f}]\nHolm p={effect['holm_adjusted_p']:.4g}; {effect['conclusion']}",ha='center',transform=axis.transAxes,fontsize=9,color='#536876')
    style(axes.flat)
    figure.text(.07,.11,'Dots: independent seed summaries; two layouts averaged within seed. Risk rates use actual living time, not total initial population time.',fontsize=10,color='#536876')
    figure.text(.07,.07,'Holm correction covers all five primary tests. Intervals are paired pointwise 95% bootstrap; individual creatures are not independent seeds.',fontsize=10,color='#536876')
    figure.text(.07,.03,'Avoidance claim requires improved fitness AND meals AND reduced collision rate or hazard exposure. New-input benefit is tested separately.',fontsize=10,color='#536876')
    return figure


def save_obstacle_plot(report,path):export(build_study_figure(report),path)


def save_layout_plot(report,path):
    if report.get('status')!='complete':raise ValueError('Visualize only a complete study.')
    analyze_results(report)
    trial=next(t for t in report['trials'] if t['seed']==report['protocol']['seeds'][0])
    test=next(x for x in trial['tests'] if x['repeat']==1)
    world=ObstacleWorld(seed=test['seed'],fixed_speed=60.0,evolution_enabled=False)
    if initial_conditions_digest(world)!=test['conditions']['evolved']['initial_conditions']:raise ValueError('Layout provenance mismatch.')
    figure=Figure(figsize=(11,7),facecolor='#f8fafc');FigureCanvasAgg(figure);axis=figure.subplots()
    figure.subplots_adjust(left=.08,right=.97,bottom=.16,top=.85)
    for b in world.barriers:axis.add_patch(Rectangle((b.x,b.y),b.width,b.height,facecolor='#657d89',edgecolor='#3f5664'))
    for h in world.dangers:axis.add_patch(Circle((h.x,h.y),h.radius,facecolor='#e7a0ad',edgecolor='#af4055',alpha=.65))
    axis.scatter([f.x for f in world.food],[f.y for f in world.food],s=9,color='#6a9b43',label='Initial food')
    axis.scatter([c.x for c in world.creatures],[c.y for c in world.creatures],s=12,color='#91a7b5',label='Matched initial bodies')
    axis.set(xlim=(0,1000),ylim=(600,0),xlabel='x (pixels)',ylabel='y (pixels)',title=f"Actual held-out layout · source seed {trial['seed']}, repeat 1")
    axis.set_aspect('equal',adjustable='box');axis.legend(frameon=False,fontsize=9,loc='upper right');style([axis])
    figure.text(.08,.08,'Grey: solid barriers; red: dangerous regions; food and newborns spawn outside both. The same geometry is used by all three conditions.',fontsize=9,color='#536876')
    figure.text(.08,.035,'First declared seed and first held-out repeat, fixed before outcomes. Food replenishes; this is the initial layout, not a trajectory.',fontsize=9,color='#536876')
    export(figure,path)


def save_lineage_plot(report,path):
    # A frame-limited run may have started an unfinished next birth cohort.
    report=copy.deepcopy(report)
    report['obstacle_environment']['history']=[r for r in report['obstacle_environment']['history'] if r['complete']]
    validate_cohorts(report,study=False);history=report['obstacle_environment']['history'];rows=report['generations']
    if not rows:raise ValueError('Complete an obstacle cohort before plotting.')
    figure=Figure(figsize=(12,8),facecolor='#f8fafc');FigureCanvasAgg(figure);axes=figure.subplots(2,2)
    figure.subplots_adjust(left=.09,right=.96,bottom=.14,top=.85,wspace=.3,hspace=.5)
    figure.suptitle(f"Obstacle lineage · seed {report['seed']} · 16-input brains",fontsize=18)
    for axis,values,title in (
        (axes[0,0],[r['mean_fitness'] for r in rows],'Penalized fitness'),
        (axes[0,1],[r['mean_food_eaten'] for r in rows],'Meals per creature'),
        (axes[1,0],[r['collision_rate'] for r in history],'Barrier collisions per living minute'),
        (axes[1,1],[r['hazard_fraction'] for r in history],'Danger exposure / living time'),
    ):
        axis.plot([r['generation'] for r in rows],values,color=COLORS[0],marker='o');axis.set(title=title,xlabel='Generation')
    style(axes.flat);figure.text(.08,.05,'Descriptive training history; geometry changes each generation. Use matched frozen held-out tests to assess evolved avoidance.',fontsize=10,color='#536876')
    export(figure,path)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('report',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--layout-output',type=Path)
    args=parser.parse_args()
    try:
        r=json.loads(args.report.read_text())
        if 'obstacle_environment' in r:save_lineage_plot(r,args.output)
        else:
            save_obstacle_plot(r,args.output)
            if args.layout_output:save_layout_plot(r,args.layout_output)
    except(ValueError,OSError)as error:parser.error(str(error))
    return 0


if __name__=='__main__':raise SystemExit(main())
