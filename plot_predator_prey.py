"""Historical opponent matrices, defensive movement, and observed live counts."""

import argparse
import copy
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'.cache/matplotlib'))

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from body_traits import shared_layout_digest
from experiment_predator_prey import analyze_results, load_models, opponent_bank, case_name, validate_cohorts
from experiment_strategy import file_digest
from plot_traits import export, style


COLORS = {'prey': '#168b78', 'predator': '#cf596c'}


def build_study_figure(report):
    if report.get('status') != 'complete': raise ValueError('Plot only a complete coevolution study.')
    a = analyze_results(report)
    f = Figure(figsize=(17, 11), facecolor='#f8fafc'); FigureCanvasAgg(f)
    axes = f.subplots(2, 3)
    f.subplots_adjust(left=.09, right=.97, top=.82, bottom=.19, wspace=.65, hspace=.6)
    f.suptitle('Predator–prey coevolution', fontsize=24, fontweight='bold', y=.97, color='#173344')
    f.text(.5,.92,f"{a['independent_seed_groups']} independent seeds · 80 prey + 20 predators · inherited brains and bodies · finite {report['protocol']['episode_seconds']:g}-second cohorts",ha='center',fontsize=12,color='#536876')
    f.text(.5,.875,'Historical opponents test reciprocal improvement. Declining capture alone can also reflect starvation.',ha='center',fontsize=11,color='#536876')
    rows = a['training']; g = [r['generation'] for r in rows]
    for species in COLORS:
        axes[0,0].plot(g,[r[species]['survival_rate'] for r in rows],color=COLORS[species],marker='o',label=species.title())
    axes[0,0].set(title='Training: alive at evaluation end',xlabel='Generation',ylabel='Fraction of births',ylim=(0,1));axes[0,0].legend(frameon=False,fontsize=8)
    axes[0,1].plot(g,[r['capture_fraction'] for r in rows],color=COLORS['predator'],marker='o')
    axes[0,1].set(title='Training: prey captured',xlabel='Generation',ylabel='Fraction of initial prey',ylim=(0,1))
    for species,metric in (('prey','away_fraction'),('predator','toward_fraction')):
        axes[0,2].plot(g,[r[species][metric] if r[species][metric] is not None else np.nan for r in rows],color=COLORS[species],marker='o',label=f"{species.title()} {'away' if species=='prey' else 'toward'}")
    axes[0,2].set(title='Observed opponent-relative movement',xlabel='Generation',ylabel='Share of visible-opponent living time',ylim=(0,1));axes[0,2].legend(frameon=False,fontsize=8)
    for column,key,title in ((0,'capture_fraction_matrix','Frozen tests: prey captured'),(1,'prey_survival_matrix','Frozen tests: prey alive at end')):
        axis = axes[1,column]; values = np.array(a[key])
        im=axis.imshow(values,vmin=0,vmax=1,cmap='YlGnBu' if column==0 else 'YlGn',aspect='auto')
        for i in range(3):
            for j in range(3):axis.text(j,i,f'{100*values[i,j]:.1f}%',ha='center',va='center',fontsize=11,color='white' if values[i,j]>.6 else '#173344')
        labels=[f'G{x}' for x in a['checkpoint_generations']]
        axis.set(xticks=range(3),xticklabels=labels,yticks=range(3),yticklabels=labels,title=title,xlabel='Prey source generation',ylabel='Predator source generation')
        axis.grid(False)
    axis=axes[1,2]
    names=['Pred / early prey','Prey / early pred','Pred / final prey','Prey / final pred']
    for i,(name,row) in enumerate(zip(names,a['primary'].values())):
        lo,hi=row['difference_ci95']; color=COLORS['predator' if i%2==0 else 'prey']
        axis.hlines(i,lo,hi,color=color,linewidth=3);axis.scatter(row['mean_difference'],i,color=color,marker='D',s=35)
    axis.axvline(0,color='#95a8b5',linestyle='--')
    axis.set_yticks(range(4),[f"{name}\np={row['holm_adjusted_p']:.4g}; {row['conclusion']}" for name,row in zip(names,a['primary'].values())],fontsize=7)
    axis.set(title='Four primary improvements',xlabel='Fraction difference; pointwise 95% interval',ylim=(3.5,-.5))
    style(axes.flat)
    for axis in axes[1,:2]:axis.grid(False)
    f.text(.065,.125,'Pred: final versus founding predators; benefit = more captures. Prey: final versus founding prey; benefit = more alive at the horizon.',fontsize=10,color='#536876')
    f.text(.065,.085,'All four use paired source-seed tests and Holm correction. Matrices and movement curves are descriptive. Birth counts reset each generation.',fontsize=10,color='#536876')
    f.text(.065,.045,f"Verdict: {a['verdict'].replace('_',' ')}. No frozen-opponent training control; this cannot establish a sustained opponent-driven arms race.",fontsize=10,color='#536876')
    return f


def save_population_plot(report,path):
    if report.get('status')!='complete':raise ValueError('Plot only a complete coevolution study.')
    analyze_results(report)
    first=next(t for t in report['trials'] if t['seed']==report['protocol']['seeds'][0])
    f=Figure(figsize=(14,10),facecolor='#f8fafc');FigureCanvasAgg(f);axes=f.subplots(2,2)
    f.subplots_adjust(left=.08,right=.96,top=.82,bottom=.14,wspace=.3,hspace=.5)
    f.suptitle('Population losses within and across cohorts',fontsize=22,fontweight='bold',y=.97)
    f.text(.5,.915,f"Top: every training cohort of predetermined seed {first['seed']}. Bottom: equal-seed mean proportions across the complete study.",ha='center',fontsize=11,color='#536876')
    from matplotlib import colormaps
    for col,species in enumerate(('prey','predator')):
        for row in first['training']['ecosystem']['history']:
            points=row['population'];g=row['generation']
            axes[0,col].plot([p['time'] for p in points],[p[species] for p in points],color=colormaps['viridis']((g-1)/max(1,report['protocol']['generations']-1)),label=f'G{g}')
        axes[0,col].set(title=f'{species.title()}: actual live counts',xlabel='Seconds within cohort',ylabel='Living individuals',ylim=(0,report['protocol']['birth_counts'][species]))
        axes[0,col].legend(ncol=4,fontsize=7,frameon=False)
        series=[]
        for status in ('alive','predation','starvation','old_age'):
            series.append([np.mean([t['training']['ecosystem']['history'][i]['species'][species]['survival_rate'] if status=='alive'
                else t['training']['ecosystem']['history'][i]['species'][species]['deaths'][status]/report['protocol']['birth_counts'][species] for t in report['trials']]) for i in range(report['protocol']['generations'])])
        axes[1,col].stackplot(range(1,report['protocol']['generations']+1),series,labels=['Alive at horizon','Predation','Starvation','Old age'],colors=['#65b8a3','#cf596c','#cfaa65','#a7b7c5'])
        axes[1,col].set(title=f'{species.title()}: fate of every newborn',xlabel='Generation',ylabel='Fraction of births',ylim=(0,1))
        axes[1,col].legend(fontsize=7,frameon=False,loc='upper left',ncol=2)
    style(axes.flat)
    f.text(.07,.075,'Living actors at the horizon are censored survivors. All dead and living genomes remain eligible for their own role’s generational selection.',fontsize=10,color='#536876')
    f.text(.07,.035,'Birth counts are controlled experimental settings. These plots do not show continuous demographic reproduction, ecological cycles, or permanent extinction.',fontsize=10,color='#536876')
    export(f,path)


def save_world_image(report,path):
    if report.get('status')!='complete':raise ValueError('Render only a complete coevolution study.')
    from predator_prey import PredatorPreyWorld
    from simulation import EvolutionSimulation
    from main import draw_interface,PADDING,HEADER_HEIGHT,FOOTER_HEIGHT
    import pygame
    first=next(t for t in report['trials'] if t['seed']==report['protocol']['seeds'][0]);g=report['protocol']['generations']
    if file_digest(first['model_file'])!=first['model_sha256']:raise ValueError('Historical archive checksum changed.')
    _,banks=load_models(first['model_file'],first['seed'],g)
    record=first['tests'][case_name(g,g)]
    world=PredatorPreyWorld(seed=record['seed'],episode_seconds=report['protocol']['episode_seconds'],evolution_enabled=False,genomes=opponent_bank(banks[g],banks[g]))
    if shared_layout_digest(world)!=record['shared_layout_sha256']:raise ValueError('Screenshot uses a different test scenario.')
    s=EvolutionSimulation(world,generation_limit=1,auto_advance=False)
    s.update(min(10.,report['protocol']['episode_seconds']))
    world.selected_creature=next((c for c in world.creatures if c.species=='prey'),None)
    os.environ['SDL_VIDEODRIVER']='dummy';pygame.display.init();pygame.font.init()
    try:
        screen=pygame.display.set_mode((world.width+2*PADDING,world.height+HEADER_HEIGHT+FOOTER_HEIGHT))
        fonts={'title':pygame.font.Font(None,38),'small':pygame.font.Font(None,20)}
        draw_interface(screen,world,fonts,s);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);pygame.image.save(screen,str(path))
    finally:pygame.quit()


def save_lineage_plot(report,path):
    report=copy.deepcopy(report)
    report['ecosystem']['history']=[h for h in report['ecosystem']['history'] if h['complete']]
    validate_cohorts(report,study=False)
    rows=report['ecosystem']['history']
    if not rows:raise ValueError('Complete a cohort before plotting.')
    f=Figure(figsize=(12,8),facecolor='#f8fafc');FigureCanvasAgg(f);axes=f.subplots(2,2)
    f.subplots_adjust(left=.09,right=.96,top=.85,bottom=.13,wspace=.3,hspace=.45)
    f.suptitle(f"Predator–prey lineage · seed {report['seed']}",fontsize=19)
    g=[r['generation'] for r in rows]
    for col,species in enumerate(COLORS):
        for row,metric,title in ((0,'survival_rate','Alive at evaluation end'),(1,'mean_fitness','Role-specific fitness')):
            axes[row,col].plot(g,[r['species'][species][metric] for r in rows],color=COLORS[species],marker='o')
            axes[row,col].set(title=f'{species.title()}: {title}',xlabel='Completed generation')
    style(axes.flat);f.text(.08,.04,'Fixed birth cohorts; within-cohort competition and losses. Training curves alone cannot establish an evolutionary arms race.',fontsize=10,color='#536876');export(f,path)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('report',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--populations-output',type=Path);parser.add_argument('--world-output',type=Path)
    args=parser.parse_args()
    try:
        report=json.loads(args.report.read_text())
        if 'ecosystem' in report:save_lineage_plot(report,args.output)
        else:
            export(build_study_figure(report),args.output)
            if args.populations_output:save_population_plot(report,args.populations_output)
            if args.world_output:save_world_image(report,args.world_output)
    except (ValueError,OSError) as error:parser.error(str(error))
    return 0


if __name__=='__main__':raise SystemExit(main())
