'''
Reference implementation of various functions. The reason this exists
is so that the user can choose to either stick with the 
'''

import numpy as np

from diffusers import StableDiffusionPipeline, StableDiffusionPipeline
from diffusers import StableDiffusionInpaintPipeline, StableDiffusionInstructPix2PixPipeline, EulerAncestralDiscreteScheduler
from diffusers import StableDiffusionControlNetPipeline, UniPCMultistepScheduler, ControlNetModel

import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
import torch

from PIL import Image
from controlnet_aux import CannyDetector, OpenposeDetector

from .layer import Layer


def dream(prompt: str, model_ckpt: str = "runwayml/stable-diffusion-v1-5", seed: int = 42, device: str = "mps", batch_size: int = 1, selected: int = 0, num_steps: int = 20, guidance_scale: float = 7.5, **kwargs):
    pipe = StableDiffusionPipeline.from_pretrained(model_ckpt, torch_dtype=torch.float32, safety_checker=None)
    pipe = pipe.to(device)
    
    generator = [torch.Generator().manual_seed(seed + i) for i in range(batch_size)]
    
    image = pipe(prompt, generator=generator, num_inference_steps=num_steps, guidance_scale=guidance_scale).images[selected]

    return Layer(image=image)


def mask_and_inpaint(mask_image: Layer, image: Layer, prompt: str, model_ckpt: str = "runwayml/stable-diffusion-inpainting", seed: int = 42, device: str = "mps", batch_size: int = 1, selected: int = 0, num_steps: int = 20, guidance_scale: float = 7.5, **kwargs):
    pipe = StableDiffusionInpaintPipeline.from_pretrained(
        model_ckpt,
        safety_checker=None,
    )
    pipe = pipe.to(device)
    
    generator = [torch.Generator().manual_seed(seed + i) for i in range(batch_size)]
    
    inpainted_image = pipe(prompt=prompt, image=image.get_image(), mask_image=mask_image.get_image(), generator=generator, num_inference_steps=num_steps, guidance_scale=guidance_scale).images[selected]

    return Layer(image=inpainted_image)


def make_dummy_mask():
    from PIL import Image, ImageDraw

    # Create a blank mask with the size of 512x512
    width, height = 512, 512
    mask = Image.new("1", (width, height))

    # Draw a simple shape on the mask using ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.rectangle([128, 128, 384, 384], fill="white")
                
    return Layer(image=mask)


def instruct_pix2pix(image_layer, prompt, device = "mps"):
    model_id = "timbrooks/instruct-pix2pix"
    pipe = StableDiffusionInstructPix2PixPipeline.from_pretrained(model_id, torch_dtype=torch.float32, safety_checker=None)
    pipe.to(device)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    
    images = pipe(prompt, image=image_layer.get_image(), num_inference_steps=10, image_guidance_scale=1).images
    return Layer(images[0])


def controlnet_canny(image_layer, prompt, device: str = "cpu", model_ckpt: str = "runwayml/stable-diffusion-v1-5", batch_size = 1, seed = 42, selected = 0, num_steps = 20, **kwargs):
    canny = CannyDetector()
    canny_image = canny(image_layer.get_image())
    
    controlnet = ControlNetModel.from_pretrained("lllyasviel/sd-controlnet-canny", torch_dtype=torch.float32)
    pipe = StableDiffusionControlNetPipeline.from_pretrained(
        model_ckpt, controlnet=controlnet, torch_dtype=torch.float32, safety_checker=None
    ).to(device)
    
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    if device == "cuda":
        pipe.enable_xformers_memory_efficient_attention()
        pipe.enable_model_cpu_offload()
    
    generator = [torch.Generator().manual_seed(seed + i) for i in range(batch_size)]
    
    controlnet_image = pipe(
        prompt,
        canny_image,
        num_inference_steps=num_steps,
        generator=generator,
    ).images[selected]
    
    return Layer(image=controlnet_image)


def controlnet_openpose(image_layer, prompt, device: str = "cpu", model_ckpt: str = "runwayml/stable-diffusion-v1-5", batch_size = 1, seed = 42, selected = 0, num_steps = 20, **kwargs):
    openpose = OpenposeDetector.from_pretrained("lllyasviel/Annotators")
    openpose_image = openpose(image_layer.get_image(), hand_and_face=True)
    
    controlnet = ControlNetModel.from_pretrained("lllyasviel/sd-controlnet-openpose", torch_dtype=torch.float32)
    pipe = StableDiffusionControlNetPipeline.from_pretrained(
        model_ckpt, controlnet=controlnet, torch_dtype=torch.float32, safety_checker=None
    ).to(device)
    
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    if device == "cuda":
        pipe.enable_xformers_memory_efficient_attention()
        pipe.enable_model_cpu_offload()
    
    generator = [torch.Generator().manual_seed(seed + i) for i in range(batch_size)]
    
    controlnet_image = pipe(
        prompt,
        openpose_image,
        num_inference_steps=num_steps,
        generator=generator,
    ).images[selected]
    
    return Layer(image=controlnet_image)
    