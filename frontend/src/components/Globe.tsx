import React, { useEffect, useRef } from "react";
import createGlobe from "cobe";
import { motion } from "framer-motion";
import { useInViewAnimation } from "../hooks/useInViewAnimation";

export const Globe = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { ref, isInView } = useInViewAnimation("-100px");

  useEffect(() => {
    let phi = 0;

    if (!canvasRef.current) return;

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: 2,
      width: 800 * 2,
      height: 800 * 2,
      phi: 0,
      theta: 0.1,
      dark: 1,
      diffuse: 1.2,
      mapSamples: 16000,
      mapBrightness: 6,
      baseColor: [0.1, 0.1, 0.1],
      markerColor: [1, 1, 1],
      glowColor: [0.2, 0.2, 0.2],
      markers: [
        { location: [40.7128, -74.0060], size: 0.05 },
        { location: [51.5074, -0.1278], size: 0.05 },
        { location: [35.6895, 139.6917], size: 0.05 },
        { location: [28.6139, 77.2090], size: 0.05 },
        { location: [25.2048, 55.2708], size: 0.05 }
      ],
      onRender: (state: any) => {
        state.phi = phi;
        phi += 0.005;
      },
    } as any);

    return () => {
      globe.destroy();
    };
  }, []);

  return (
    <section className="relative w-full overflow-hidden bg-black py-24 flex items-center justify-center min-h-[600px] border-t border-white/5" ref={ref}>
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={isInView ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.9 }}
        transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-[800px] aspect-square flex items-center justify-center mx-auto"
      >
        <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black to-transparent z-10 pointer-events-none" />
        <canvas
          ref={canvasRef}
          style={{ width: 800, height: 800, maxWidth: "100%", aspectRatio: 1 }}
          className="opacity-80"
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full text-center z-20 pointer-events-none">
          <p className="text-white/40 tracking-[0.2em] text-sm font-medium uppercase drop-shadow-lg">Global Capital Network</p>
        </div>
      </motion.div>
    </section>
  );
};
