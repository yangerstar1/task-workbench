"""Deterministic CC0 base-color illumination correction. No engine or generated noise.
Requires Python, Pillow and NumPy. Original source bytes are read-only.
Usage: python correct_illumination.py SOURCE_JPEG OUTPUT_PNG
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
SOURCE_SHA='e72144f9d7b81bdb7bbdb34222b53431738dcef79346dd89412d2abd541e4d30'
SIGMA_PIXELS=48.0
WEIGHTS=np.array([.2126,.7152,.0722])
def linear(a):return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
def srgb(a):return np.where(a<=.0031308,a*12.92,1.055*np.maximum(a,0)**(1/2.4)-.055)
def metrics(rgb):
 y=rgb@WEIGHTS;f=np.fft.fft2(y-y.mean())/y.size;fy=np.fft.fftfreq(y.shape[0])*y.shape[0];fx=np.fft.fftfreq(y.shape[1])*y.shape[1]
 k=np.sqrt(fy[:,None]**2+fx[None,:]**2)
 return {'mean_linear_rgb':rgb.mean(axis=(0,1)).tolist(),'relative_luminance_std':float(y.std()/y.mean()),'x_fundamental_amplitude_fraction':float(2*abs(f[0,1])/y.mean()),'z_fundamental_amplitude_fraction':float(2*abs(f[1,0])/y.mean()),'low_frequency_rms_fraction_le4':float(np.sqrt((abs(f[k<=4])**2).sum())/y.mean()),'grain_rms_fraction_ge16':float(np.sqrt((abs(f[k>=16])**2).sum())/y.mean())}
def correct(source,destination):
 source=Path(source);destination=Path(destination)
 if hashlib.sha256(source.read_bytes()).hexdigest()!=SOURCE_SHA:raise ValueError('Exact CC0 source SHA required')
 if destination.exists() or source.resolve()==destination.resolve():raise ValueError('Never overwrite existing output or original source')
 with Image.open(source) as image:
  if image.size!=(1024,1024) or image.mode!='RGB':raise ValueError('Expected original 1K RGB source')
  rgb=linear(np.asarray(image,dtype=np.float64)/255)
 y=rgb@WEIGHTS;n=y.shape[0];freq=np.fft.fftfreq(n)
 gaussian=np.exp(-2*np.pi**2*SIGMA_PIXELS**2*(freq[:,None]**2+freq[None,:]**2))
 illumination=np.fft.ifft2(np.fft.fft2(y)*gaussian).real
 gain=y.mean()/illumination
 if not np.isfinite(gain).all() or gain.min()<.75 or gain.max()>1.25:raise ValueError('Unexpected illumination correction magnitude')
 corrected=rgb*gain[...,None]
 corrected*=rgb.mean(axis=(0,1))/corrected.mean(axis=(0,1))
 if (corrected<0).any() or (corrected>1).any():raise ValueError('Correction would clip color data')
 encoded=np.round(srgb(corrected)*255).clip(0,255).astype(np.uint8)
 destination.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(encoded,'RGB').save(destination,format='PNG',compress_level=9)
 actual=linear(encoded.astype(np.float64)/255)
 before,after=metrics(rgb),metrics(actual)
 if after['low_frequency_rms_fraction_le4']>=before['low_frequency_rms_fraction_le4']*.2:raise ValueError('Low-frequency correction ineffective')
 if not .95<after['grain_rms_fraction_ge16']/before['grain_rms_fraction_ge16']<1.05:raise ValueError('Fine grain was not preserved')
 return {'source_sha256':SOURCE_SHA,'derived_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'derived_bytes':destination.stat().st_size,'sigma_pixels':SIGMA_PIXELS,'tile_metres':2,'spatial_sigma_metres':SIGMA_PIXELS/1024*2,'illumination_gain_range':[float(gain.min()),float(gain.max())],'before':before,'after':after}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');args=p.parse_args();print(json.dumps(correct(args.source,args.destination),indent=2))
