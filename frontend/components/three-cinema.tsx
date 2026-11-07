"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

/** A compact, self-contained Three.js composition. The canvas is decorative;
 * title actions stay in normal DOM for keyboard and screen-reader access. */
export default function ThreeCinema({ title, artwork = [] }: { title: string; artwork?: (string | undefined)[] }) {
  const mount = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const host = mount.current;
    if (!host) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    camera.position.set(0, 0, 8.4);
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" }); }
    catch { host.classList.add("webgl-unavailable"); return () => host.classList.remove("webgl-unavailable"); }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setSize(host.clientWidth, host.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);
    scene.add(new THREE.AmbientLight(0x9cb2d4, 1.8));
    const key = new THREE.PointLight(0xc6a66a, 24, 18); key.position.set(3, 3, 5); scene.add(key);
    const fill = new THREE.PointLight(0x5672a0, 15, 16); fill.position.set(-4, -1, 2); scene.add(fill);
    const makePoster = (label: string, hue: number) => {
      const canvas = document.createElement("canvas"); canvas.width = 512; canvas.height = 768;
      const ctx = canvas.getContext("2d")!;
      const g = ctx.createLinearGradient(0, 0, 512, 768); g.addColorStop(0, `hsl(${hue} 38% 28%)`); g.addColorStop(.5, "#12151d"); g.addColorStop(1, "#08090c");
      ctx.fillStyle = g; ctx.fillRect(0, 0, 512, 768);
      ctx.fillStyle = `hsla(${hue} 55% 68% / .55)`; ctx.beginPath(); ctx.arc(340, 250, 150, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,.82)"; ctx.font = "500 36px Georgia"; ctx.fillText("MANU · SELECTED", 38, 660);
      ctx.fillStyle = "#fff"; ctx.font = "600 46px Georgia";
      const words = label.toUpperCase().split(" "); let y = 570;
      for (const word of words.slice(0, 3)) { ctx.fillText(word, 38, y); y += 53; }
      const tex = new THREE.CanvasTexture(canvas); tex.colorSpace = THREE.SRGBColorSpace;
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2.05, 3.08), new THREE.MeshPhysicalMaterial({ map: tex, roughness: .4, metalness: .08, clearcoat: .36 }));
      return mesh;
    };
    const cards = [makePoster(title, 38), makePoster("Curated stories", 214), makePoster("After dark", 173)];
    const loader = new THREE.TextureLoader(); loader.setCrossOrigin("anonymous");
    const textures: THREE.Texture[] = [];
    artwork.filter((url): url is string => Boolean(url && /^https:\/\//.test(url))).slice(0, 2).forEach((url, index) => {
      const textureUrl = `/api/artwork?src=${encodeURIComponent(url)}`;
      loader.load(textureUrl, texture => {
        texture.colorSpace = THREE.SRGBColorSpace;
        textures.push(texture);
        const material = cards[index].material as THREE.MeshPhysicalMaterial;
        const old = material.map; material.map = texture; material.needsUpdate = true; old?.dispose();
      }, undefined, () => undefined);
    });
    cards.forEach((card, i) => { card.position.set((i - 1) * 1.55, i === 1 ? .18 : -.12, -Math.abs(i - 1) * .7); card.rotation.y = (i - 1) * -.13; scene.add(card); });
    const resize = () => { if (!host.clientWidth) return; camera.aspect = host.clientWidth / host.clientHeight; camera.updateProjectionMatrix(); renderer.setSize(host.clientWidth, host.clientHeight); };
    const observer = new ResizeObserver(resize); observer.observe(host);
    let frame = 0; let pointerX = 0;
    const onMove = (e: PointerEvent) => { pointerX = (e.clientX / window.innerWidth - .5) * .32; };
    window.addEventListener("pointermove", onMove, { passive: true });
    const draw = () => { frame = requestAnimationFrame(draw); if (!reduce) { camera.position.x += (pointerX - camera.position.x) * .025; cards.forEach((c, i) => { c.position.y = (i === 1 ? .18 : -.12) + Math.sin(Date.now() * .0005 + i) * .045; }); } renderer.render(scene, camera); };
    draw();
    return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener("pointermove", onMove); cards.forEach(c => { (c.material as THREE.Material).dispose(); c.geometry.dispose(); }); textures.forEach(texture => texture.dispose()); renderer.dispose(); host.replaceChildren(); };
  }, [title, artwork]);
  return <div className="three-cinema" ref={mount} aria-hidden="true" />;
}
