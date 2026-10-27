#!/usr/bin/env python3
"""Resize/compress actual captures and encode timestamped GIF/H.264 excerpts.

No generated pixels, scene replacement, retouching, overlays or frame interpolation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import statistics
import subprocess

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_frame(path,record):
    if record.get('storage_format')=='RGBA8':
        size=tuple(record['pixels']);data=path.read_bytes()
        if len(data)!=size[0]*size[1]*4:raise ValueError('Truncated raw capture: '+str(path))
        return Image.frombytes('RGBA',size,data).convert('RGB')
    with Image.open(path) as image:return image.convert('RGB')


def scaled(image,width):
    result=image.copy();result.thumbnail((width,round(image.height*width/image.width)),Image.Resampling.LANCZOS)
    return result


def save_still(source,target,width,quality):
    with Image.open(source) as image:
        output=scaled(image.convert('RGB'),width)
        output.save(target,'JPEG',quality=quality,subsampling=0,optimize=True,progressive=True)
        return dict(file=target.name,width=output.width,height=output.height,bytes=target.stat().st_size,
                    sha256=digest(target),source_png_sha256=digest(source),source_bytes=source.stat().st_size,
                    processing='Full viewport; resize and JPEG compression only; no cropping or retouching')


def encode_gif(source,rows,target,width):
    images=[scaled(load_frame(source/row['file'],row),width) for row in rows]
    sample=images[::max(1,len(images)//8)][:8]
    palette_strip=Image.new('RGB',(images[0].width,images[0].height*len(sample)))
    for i,image in enumerate(sample):palette_strip.paste(image,(0,i*image.height))
    palette=palette_strip.quantize(colors=128,method=Image.Quantize.MEDIANCUT)
    quantized=[image.quantize(palette=palette,dither=Image.Dither.NONE) for image in images]
    times=[row['wall_seconds']-rows[0]['wall_seconds'] for row in rows]
    step=statistics.median(b-a for a,b in zip(times,times[1:]))
    end=times[-1]+step
    boundaries=[round(t*100)*10 for t in [*times,end]]
    durations=[max(10,b-a) for a,b in zip(boundaries,boundaries[1:])]
    quantized[0].save(target,save_all=True,append_images=quantized[1:],loop=0,duration=durations,
                      optimize=True,disposal=1)
    with Image.open(target) as output:
        assert output.n_frames>1
        seconds=0
        for index in range(output.n_frames):output.seek(index);seconds+=output.info.get('duration',0)/1000
    return dict(file=target.name,width=images[0].width,height=images[0].height,bytes=target.stat().st_size,
                frames=len(rows),duration_seconds=round(seconds,3),sha256=digest(target),looped=True,
                source_frame_files=[row['file'] for row in rows],
                processing='Resized/128-color sampled preview; original capture timestamps; no interpolated frames')


def encode_movie(source,rows,target,cache,encoder):
    cache.mkdir(parents=True,exist_ok=True)
    first=load_frame(source/rows[0]['file'],rows[0]);width=min(1280,first.width)//2*2;height=round(first.height*width/first.width)//2*2
    times=[row['wall_seconds']-rows[0]['wall_seconds'] for row in rows]
    duration=times[-1]+statistics.median(b-a for a,b in zip(times,times[1:]))
    frames=[]
    for index,row in enumerate(rows):
        image=load_frame(source/row['file'],row).resize((width,height),Image.Resampling.LANCZOS)
        file=cache/f'frame-{index:04d}.jpg';image.save(file,'JPEG',quality=96,subsampling=0)
        frames.append(dict(file=str(file),seconds=times[index]))
    plan=dict(output=str(target),width=width,height=height,duration=duration,frames=frames,verification_dir=str(cache/'verify'))
    path=cache/'encode.json';path.write_text(json.dumps(plan,indent=2)+'\n')
    subprocess.run([str(encoder),str(path)],check=True)
    inspected=json.loads((cache/'verify/inspection.json').read_text())
    if inspected['codec']!='avc1' or abs(inspected['duration_seconds']-duration)>.2:raise ValueError('Video verification failed')
    errors=[]
    for label,index in [('first',0),('last',len(rows)-1)]:
        actual=np.asarray(Image.open(cache/'verify'/f'{label}.png').convert('RGB'),dtype=float)
        expected=np.asarray(Image.open(frames[index]['file']).convert('RGB'),dtype=float)
        errors.append(float(np.mean(np.abs(actual-expected))))
    if max(errors)>12:raise ValueError('Encoded video differs too much from actual source frames: '+str(errors))
    return dict(file=target.name,width=width,height=height,bytes=target.stat().st_size,frames=len(rows),
                duration_seconds=duration,sha256=digest(target),codec='H.264 / avc1',silent=True,
                endpoint_mean_absolute_pixel_error=errors,processing='Full viewport; resize and H.264 compression; measured capture timestamps')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'v2/docs/media/gallery')
    parser.add_argument('--cases',nargs='*')
    args=parser.parse_args();raw=args.raw.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'.cache/documentation-media/encoding';cache.mkdir(parents=True,exist_ok=True)
    encoder=cache/'encode-video'
    subprocess.run(['swiftc','-suppress-warnings',str(ROOT/'v2/tools/encode_documentation.swift'),'-o',str(encoder)],check=True)
    cases=[]
    for path in sorted(raw.glob('*/capture.json')):
        source=path.parent;capture=json.loads(path.read_text());name=capture['case']
        if args.cases and name not in args.cases:continue
        if not capture.get('verified_and_replayed'):raise ValueError(name+' lacks a successful source replay')
        report=json.loads((Path(capture['bundle'])/'run.json').read_text())
        still=save_still(source/'application.png',out/(name+'.jpg'),1440,88)
        thumb=save_still(source/'application.png',out/(name+'-thumb.jpg'),720,82)
        commit=capture.get('source_commit') or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        tool_hash=capture.get('capture_tool_sha256') or digest(ROOT/'v2/tools/capture_gallery.py')
        row=dict(case=name,source=capture['source'],renderer=capture['renderer'],source_commit=commit,
                 headless=capture['headless'],device=capture.get('device'),platform=capture.get('platform'),
                 still=still,thumbnail=thumb,still_state=capture['still'],ecosystem=capture.get('ecosystem'),configuration=report['config'],physical_habitat=report.get('habitat',{}).get('config'),
                 presentation=capture.get('plan',{}),ticks=report['execution']['ticks'],metrics=report['metrics'],
                 actual_events=capture.get('animation',{}).get('events',{}),event_gaps=capture.get('event_gaps',0),
                 exact_numerical_replay=True,capture_tool_sha256=tool_hash)
        row['still_state']={k:v for k,v in row['still_state'].items() if k!='file'}
        row['presentation']={k:v for k,v in row['presentation'].items() if k not in ('output','config_path')}
        frames=capture['frames']
        if frames:
            row['source_frames']=[dict(**frame,sha256=digest(source/frame['file'])) for frame in frames]
            preview=frames[::2]
            if name not in ('controls','v1-original'):
                preview=[row for row in preview if row['wall_seconds']-frames[0]['wall_seconds']<3.0]
            gif=encode_gif(source,preview,out/(name+'.gif'),480)
            if gif['bytes']>2_500_000:gif=encode_gif(source,preview,out/(name+'.gif'),400)
            if gif['bytes']>2_500_000:raise ValueError(name+' GIF exceeds documentation size budget')
            row['gif']=gif
            row['video']=encode_movie(source,frames,out/(name+'.mp4'),cache/name,encoder)
        cases.append(row);print(name,':',still['bytes'],'byte still;',row.get('gif',{}).get('bytes',0),'byte GIF',flush=True)
    manifest=dict(schema_version=1,source='Actual native application viewports; no image generation or art-stage substitution',
                  original_frame_storage='Lossless PNG stills; lossless RGBA8 Godot recording frames; original Pygame PNG recording frames',
                  preview_policy='Only resizing, JPEG/GIF/H.264 compression and explicitly sampled GIFs; no crops, overlays, retouching or generated/interpolated frames',
                  cases=cases)
    (out/'captures.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
