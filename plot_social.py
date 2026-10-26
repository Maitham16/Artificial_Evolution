"""Social survival comparisons, transfer benefits, and a declared arena replay."""
import argparse
import copy
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'.cache/matplotlib'))
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from body_traits import shared_layout_digest
from experiment_social import analyze_results,load_models,validate_cohorts
from experiment_strategy import file_digest
from plot_traits import export,style


COLORS={'group':'#158775','individual':'#a36aab'}


def build_study_figure(report):
    if report.get('status')!='complete':raise ValueError('Plot only a complete social study.')
    a=analyze_results(report);f=Figure(figsize=(17,11),facecolor='#f8fafc');FigureCanvasAgg(f);axes=f.subplots(2,3)
    f.subplots_adjust(left=.09,right=.97,top=.82,bottom=.18,wspace=.65,hspace=.65)
    f.suptitle('Does useful cooperation evolve?',fontsize=24,fontweight='bold',y=.97,color='#173344')
    f.text(.5,.92,f"{a['independent_seed_groups']} independent seeds · matched individual/group selection · 10 groups of 10 · fixed bodies",ha='center',fontsize=12,color='#536876')
    f.text(.5,.875,'Fitness rewards survival only. Transfers lose 20%; signaling costs energy. Restricted access creates a deliberate redistribution opportunity.',ha='center',fontsize=10,color='#536876')
    training=a['training'];g=[r['generation'] for r in training]
    for col,metric,title,ylabel in ((0,'mean_age','Training: actual survival','Mean age (seconds)'),
        (1,'shared_received_per_birth','Training: food energy received','Energy per newborn'),
        (2,'signal_power_per_living_second','Training: signaling expenditure','Energy per living second')):
        for arm in COLORS:axes[0,col].plot(g,[r[arm][metric] for r in training],color=COLORS[arm],marker='o',label=arm.title())
        axes[0,col].set(title=title,xlabel='Generation',ylabel=ylabel);axes[0,col].set_xticks(g)
        if col==0:axes[0,col].legend(frameon=False,fontsize=8)
    for col,key,title in ((0,'group_vs_individual','Group − individual selection'),(1,'final_sharing_benefit','Does final sharing improve survival?'),
                          (2,'evolved_sharing_gain','Did sharing benefit increase through evolution?')):
        axis=axes[1,col];labels=[]
        for i,(env,data) in enumerate(a['environments'].items()):
            row=data['primary'][key];lo,hi=row['difference_ci95'];color=('#158775','#b17d2e')[i]
            axis.hlines(i,lo,hi,color=color,linewidth=3);axis.scatter(row['mean_difference'],i,color=color,marker='D',s=40)
            labels.append(f"{env.title()}\np={row['holm_adjusted_p']:.4g}; {row['conclusion']}")
        axis.axvline(0,color='#8fa4b2',linestyle='--');axis.set_yticks([0,1],labels,fontsize=7)
        axis.set(title=title,xlabel='Mean-age difference; pointwise 95% interval',ylim=(1.5,-.5))
    style(axes.flat)
    f.text(.065,.12,'Right: (final intact − final sharing blocked) − (founder intact − founder sharing blocked). All six primary tests use Holm correction.',fontsize=10,color='#536876')
    f.text(.065,.08,'Group breeding preserves teams; individual breeding mixes selected actors. These policies differ in both incentives and assortment.',fontsize=10,color='#536876')
    f.text(.065,.04,f"Verdict: {a['verdict'].replace('_',' ')}. Restricted-access results do not establish cooperation in an unrestricted ecology.",fontsize=10,color='#536876')
    return f


def save_outcome_plot(report,path):
    if report.get('status')!='complete':raise ValueError('Plot only a complete social study.')
    a=analyze_results(report);f=Figure(figsize=(14,9),facecolor='#f8fafc');FigureCanvasAgg(f);axes=f.subplots(2,2)
    f.subplots_adjust(left=.09,right=.96,top=.82,bottom=.17,wspace=.3,hspace=.6)
    f.suptitle('Frozen social policies on unseen groups',fontsize=22,fontweight='bold',y=.97)
    f.text(.5,.915,'Every case uses all 100 individuals. Signals-hidden masks information; sharing-blocked removes physical transfers.',ha='center',fontsize=11,color='#536876')
    conditions=('founder','individual','group','group_no_sharing','group_signals_hidden');labels=['Founder','Individual','Group','Group\nno sharing','Group\nsignals hidden']
    for col,(env,data) in enumerate(a['environments'].items()):
        for row,metric,title in ((0,'mean_age','Mean survival'),(1,'shared_received_per_birth','Actual energy received')):
            values=[data['condition_means'][c][metric] for c in conditions]
            axes[row,col].bar(range(5),values,color=['#a8b7c3','#a36aab','#158775','#d3af68','#7bb4b9'])
            axes[row,col].set_xticks(range(5),labels,fontsize=8);axes[row,col].set(title=f'{env.title()}: {title}',ylabel='Seconds' if row==0 else 'Energy per newborn')
    style(axes.flat)
    f.text(.07,.10,'Open access gives every individual plant access; restricted access randomly assigns access to half the members of each isolated group.',fontsize=10,color='#536876')
    f.text(.07,.05,'Bars are descriptive equal-seed means. Formal comparisons, founder-adjusted sharing effects, and pointwise intervals are in the companion figure.',fontsize=10,color='#536876')
    export(f,path)


def save_world_image(report,path):
    if report.get('status')!='complete':raise ValueError('Render only a complete social study.')
    from social import SocialWorld
    from simulation import EvolutionSimulation
    from main import draw_interface,PADDING,HEADER_HEIGHT,FOOTER_HEIGHT
    import pygame
    t=next(t for t in report['trials'] if t['seed']==report['protocol']['seeds'][0])
    if file_digest(t['model_file'])!=t['model_sha256']:raise ValueError('Social archive checksum changed.')
    _,banks=load_models(t['model_file'],t['seed'],report['protocol']['generations']);record=t['tests']['restricted']['group']
    w=SocialWorld(seed=record['seed'],episode_seconds=report['protocol']['episode_seconds'],evolution_enabled=False,genomes=banks['group'])
    if shared_layout_digest(w)!=record['shared_layout_sha256']:raise ValueError('Social replay uses a different layout.')
    s=EvolutionSimulation(w,generation_limit=1,auto_advance=False);s.update(min(10.,report['protocol']['episode_seconds']))
    w.selected_creature=next(iter(w.creatures),None)
    os.environ['SDL_VIDEODRIVER']='dummy';pygame.display.init();pygame.font.init()
    try:
        screen=pygame.display.set_mode((w.width+2*PADDING,w.height+HEADER_HEIGHT+FOOTER_HEIGHT))
        fonts={'title':pygame.font.Font(None,38),'small':pygame.font.Font(None,20)};draw_interface(screen,w,fonts,s)
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);pygame.image.save(screen,str(path))
    finally:pygame.quit()


def save_lineage_plot(report,path):
    report=copy.deepcopy(report);report['social']['history']=[h for h in report['social']['history'] if h['complete']]
    validate_cohorts(report,study=False);rows=report['social']['history']
    if not rows:raise ValueError('Complete a social cohort before plotting.')
    f=Figure(figsize=(12,8),facecolor='#f8fafc');FigureCanvasAgg(f);axes=f.subplots(2,2)
    f.subplots_adjust(left=.1,right=.96,top=.85,bottom=.13,wspace=.3,hspace=.5);f.suptitle(f"Social lineage · seed {report['seed']} · {report['social']['selection_level']} selection",fontsize=19)
    for axis,key,title in zip(axes.flat,('mean_age','survival_rate','shared_in','signal_energy'),('Mean survival (s)','Alive at horizon','Shared energy received','Signal energy spent')):
        axis.plot([r['generation'] for r in rows],[r[key] for r in rows],color=COLORS['group'],marker='o');axis.set(title=title,xlabel='Completed generation')
    style(axes.flat);f.text(.08,.04,'Fixed reference bodies and birth groups. Action counts and training trends alone do not establish evolved beneficial cooperation.',fontsize=10,color='#536876');export(f,path)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('report',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--outcomes-output',type=Path);parser.add_argument('--world-output',type=Path);args=parser.parse_args()
    try:
        r=json.loads(args.report.read_text())
        if 'social' in r:save_lineage_plot(r,args.output)
        else:
            export(build_study_figure(r),args.output)
            if args.outcomes_output:save_outcome_plot(r,args.outcomes_output)
            if args.world_output:save_world_image(r,args.world_output)
    except (ValueError,OSError) as error:parser.error(str(error))
    return 0


if __name__=='__main__':raise SystemExit(main())
