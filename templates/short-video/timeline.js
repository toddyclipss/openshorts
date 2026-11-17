/**
 * HyperFrames Short Video Timeline Engine (OpenShorts)
 * Deterministic GSAP Timeline Factory for 1080x1920 (9:16) Viral Videos
 */

(function () {
  const RTL_CHARS = /[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]/;

  /**
   * Groups a list of word captions into cohesive subtitle blocks
   * Mirrors OpenShorts SRT and Remotion block grouping logic
   */
  function groupCaptionsIntoBlocks(captions, maxChars = 20, maxDurationMs = 2000) {
    if (!captions || captions.length === 0) return [];

    const blocks = [];
    let currentWords = [];
    let currentChars = 0;
    let blockStartMs = 0;

    for (let i = 0; i < captions.length; i++) {
      const word = captions[i];
      const wordLen = word.text.length + 1; // including space
      const wordDuration = word.endMs - blockStartMs;

      if (
        currentWords.length > 0 &&
        (currentChars + wordLen > maxChars || wordDuration > maxDurationMs)
      ) {
        blocks.push({
          startMs: blockStartMs,
          endMs: currentWords[currentWords.length - 1].endMs,
          words: currentWords,
        });
        currentWords = [];
        currentChars = 0;
      }

      if (currentWords.length === 0) {
        blockStartMs = word.startMs;
      }

      currentWords.push(word);
      currentChars += wordLen;
    }

    if (currentWords.length > 0) {
      blocks.push({
        startMs: blockStartMs,
        endMs: currentWords[currentWords.length - 1].endMs,
        words: currentWords,
      });
    }

    return blocks;
  }

  /**
   * Initializes the deterministic HyperFrames composition
   * @param {Object} props - ViralHyperFramesProps
   */
  async function initHyperFramesComposition(props) {
    // 1. Await font readiness to eliminate font flashing/FOUT in Headless Chrome
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }

    const fps = props.fps || 30;
    const durationInFrames = props.durationInFrames || 150;
    const totalDurationSec = durationInFrames / fps;

    // 2. Instantiate paused master GSAP timeline
    if (window.__timelines && window.__timelines["root"]) {
      window.__timelines["root"].kill();
    }
    const tl = gsap.timeline({ paused: true, defaults: { ease: "none" } });
    window.__timelines = window.__timelines || {};
    window.__timelines["root"] = tl;

    // 2.5 Viral Retention Progress Bar
    const retentionBar = document.getElementById("retention-bar");
    const retentionWrapper = document.getElementById("retention-bar-wrapper");
    if (retentionBar && retentionWrapper) {
      const rConf = props.retentionBar || { enabled: true };
      if (rConf.enabled !== false) {
        retentionWrapper.className = `retention-pos-${rConf.position || "top"}`;
        if (rConf.heightPx) retentionBar.style.height = `${rConf.heightPx}px`;
        if (rConf.color) retentionBar.style.background = rConf.color;
        tl.fromTo(retentionBar,
          { scaleX: 0 },
          { scaleX: 1, duration: totalDurationSec, ease: "none" },
          0
        );
      } else {
        retentionWrapper.style.display = "none";
      }
    }

    // 3. Base Video Setup
    const video = document.getElementById("base-video");
    const videoWrapper = document.getElementById("video-wrapper");

    if (props.videoUrl && video) {
      video.src = props.videoUrl;
      // Seek video deterministically frame-by-frame
      tl.to(video, {
        currentTime: totalDurationSec,
        duration: totalDurationSec,
        ease: "none"
      }, 0);
    }

    // 4. Dynamic Camera & Visual Effects (Zooms, Pans, Contrast/Saturation)
    if (props.effects && Array.isArray(props.effects.segments) && videoWrapper) {
      props.effects.segments.forEach((seg) => {
        const startSec = Math.max(0, seg.startSec);
        const transSec = seg.transitionSec || 0.3;
        const centerX = seg.zoomCenterX != null ? seg.zoomCenterX * 100 : 50;
        const centerY = seg.zoomCenterY != null ? seg.zoomCenterY * 100 : 40;
        const zoom = seg.zoom || 1.0;
        const brightness = seg.brightness || 1.0;
        const contrast = seg.contrast || 1.0;
        const saturate = seg.saturate || 1.0;
        const ease = seg.easing || "power2.out";

        tl.to(videoWrapper, {
          scale: zoom,
          transformOrigin: `${centerX}% ${centerY}%`,
          filter: `brightness(${brightness}) contrast(${contrast}) saturate(${saturate})`,
          duration: transSec,
          ease: ease
        }, startSec);

        // Screen shake for dynamic impact on #screen-shake-wrapper
        const shakeWrapper = document.getElementById("screen-shake-wrapper") || videoWrapper;
        if (seg.screenShake && shakeWrapper) {
          tl.to(shakeWrapper, {
            x: "+=14",
            y: "-=10",
            duration: 0.04,
            repeat: 5,
            yoyo: true,
            ease: "power1.inOut"
          }, startSec);
          tl.to(shakeWrapper, { x: 0, y: 0, duration: 0.04 }, startSec + 0.24);
        }
      });
    }

    // 4.5 Media Treatment Overlay (Film Grain, Vignette, CRT)
    const treatmentOverlay = document.getElementById("treatment-overlay");
    if (treatmentOverlay) {
      const treatment = props.treatment || (props.effects && props.effects.treatment);
      if (treatment) {
        treatmentOverlay.className = `treatment-${treatment}`;
      } else {
        treatmentOverlay.className = "";
      }
    }

    // 5. Dynamic Viral Hook Headline
    const hookWrapper = document.getElementById("hook-wrapper");
    const hookBox = document.getElementById("hook-box");
    const hookText = document.getElementById("hook-text");

    if (props.hook && props.hook.text && hookWrapper && hookBox && hookText) {
      hookWrapper.className = `hook-pos-${props.hook.position || "top"}`;
      hookBox.className = `hook-style-${props.hook.style || "pill"} hook-size-${props.hook.size || "M"}`;
      hookText.textContent = props.hook.text;

      const hookDuration = props.hook.displayDurationSec || 3.5;
      const entranceAnim = props.hook.entranceAnimation || "spring";

      // Entrance animation at 0s
      if (entranceAnim === "spring") {
        tl.fromTo(hookBox,
          { scale: 0.65, opacity: 0, y: -30 },
          { scale: 1.0, opacity: 1, y: 0, duration: 0.5, ease: "back.out(1.8)" },
          0
        );
      } else if (entranceAnim === "fade") {
        tl.fromTo(hookBox,
          { opacity: 0 },
          { opacity: 1, duration: 0.4, ease: "power2.out" },
          0
        );
      } else if (entranceAnim === "slide-up") {
        tl.fromTo(hookBox,
          { opacity: 0, y: 60 },
          { opacity: 1, y: 0, duration: 0.45, ease: "power2.out" },
          0
        );
      } else if (entranceAnim === "pop") {
        tl.fromTo(hookBox,
          { scale: 0.3, opacity: 0 },
          { scale: 1.0, opacity: 1, duration: 0.35, ease: "back.out(2)" },
          0
        );
      } else {
        tl.set(hookBox, { opacity: 1 }, 0);
      }

      // Exit fade-out
      const fadeOutSec = 0.35;
      const exitStart = Math.max(0.2, hookDuration - fadeOutSec);
      tl.to(hookBox, {
        opacity: 0,
        y: -15,
        duration: fadeOutSec,
        ease: "power2.in"
      }, exitStart);

      tl.set(hookWrapper, { display: "none" }, hookDuration);
    } else if (hookWrapper) {
      hookWrapper.style.display = "none";
    }

    // 5.5 Floating Emojis, Stickers & Reaction Badges Layer
    const stickersWrapper = document.getElementById("stickers-wrapper");
    if (stickersWrapper && Array.isArray(props.stickers)) {
      stickersWrapper.innerHTML = "";
      props.stickers.forEach((sticker, sIdx) => {
        const sEl = document.createElement("div");
        sEl.className = "viral-sticker";
        sEl.id = `sticker-${sIdx}`;
        const posX = (sticker.positionX != null ? sticker.positionX : 0.5) * 1080;
        const posY = (sticker.positionY != null ? sticker.positionY : 0.35) * 1920;
        sEl.style.left = `${posX}px`;
        sEl.style.top = `${posY}px`;
        sEl.style.transform = "translate(-50%, -50%)";

        if (sticker.emoji) {
          const emojiSpan = document.createElement("span");
          emojiSpan.className = "viral-sticker-emoji";
          emojiSpan.textContent = sticker.emoji;
          if (sticker.sizePx) emojiSpan.style.fontSize = `${sticker.sizePx}px`;
          sEl.appendChild(emojiSpan);
        } else if (sticker.imageUrl) {
          const img = document.createElement("img");
          img.src = sticker.imageUrl;
          img.style.width = `${sticker.sizePx || 120}px`;
          sEl.appendChild(img);
        }

        stickersWrapper.appendChild(sEl);

        const startSec = Math.max(0, sticker.startSec || 0);
        const durSec = sticker.durationSec || 2.0;
        const anim = sticker.animation || "pop";

        tl.set(sEl, { opacity: 0, scale: 0 }, 0);

        if (anim === "bounce") {
          tl.fromTo(sEl,
            { scale: 0.3, y: -40, opacity: 0 },
            { scale: 1.0, y: 0, opacity: 1, duration: 0.35, ease: "bounce.out" },
            startSec
          );
        } else {
          tl.fromTo(sEl,
            { scale: 0.2, opacity: 0 },
            { scale: 1.25, opacity: 1, duration: 0.25, ease: "back.out(2.2)" },
            startSec
          );
          tl.to(sEl, { scale: 1.0, duration: 0.15 }, startSec + 0.25);
        }

        const exitStart = Math.max(startSec + 0.2, startSec + durSec - 0.25);
        tl.to(sEl, { scale: 0.7, opacity: 0, duration: 0.25, ease: "power2.in" }, exitStart);
        tl.set(sEl, { display: "none" }, startSec + durSec);
      });
    }

    // 6. Animated Word Subtitles (Karaoke / Pop)
    const subWrapper = document.getElementById("subtitles-wrapper");
    const subContainer = document.getElementById("subtitles-container");

    if (props.subtitles && Array.isArray(props.subtitles.captions) && subWrapper && subContainer) {
      subContainer.innerHTML = "";
      subWrapper.className = `subtitles-pos-${props.subtitles.position || "bottom"}`;

      const style = props.subtitles.style || {};
      const fontFamily = style.fontFamily || "Montserrat-ExtraBold";
      const fontSize = style.fontSize || 68;
      const fontColor = style.fontColor || "#FFFFFF";
      const highlightColor = style.highlightColor || "#FFE600";
      const highlightTextColor = style.highlightTextColor || "#000000";
      const animation = style.animation || "karaoke";
      const baseOpacity = style.baseOpacity != null ? style.baseOpacity : 0.4;
      const isUppercase = style.uppercase !== false;
      const reveal = !!style.reveal;
      const borderWidth = style.borderWidth || 0;
      const borderColor = style.borderColor || "#000000";
      const shadow = style.shadow || 0;

      // Stroke & shadow CSS
      const strokeShadow = borderWidth > 0
        ? [
            `${borderWidth}px 0 0 ${borderColor}`,
            `-${borderWidth}px 0 0 ${borderColor}`,
            `0 ${borderWidth}px 0 ${borderColor}`,
            `0 -${borderWidth}px 0 ${borderColor}`,
            `${borderWidth * 0.7}px ${borderWidth * 0.7}px 0 ${borderColor}`,
            `-${borderWidth * 0.7}px -${borderWidth * 0.7}px 0 ${borderColor}`
          ].join(", ")
        : "none";

      const dropShadow = shadow > 0
        ? `${shadow * 3}px ${shadow * 3}px ${shadow * 2}px rgba(0,0,0,0.6)`
        : "";

      const combinedTextShadow = [strokeShadow !== "none" ? strokeShadow : "", dropShadow]
        .filter(Boolean)
        .join(", ");

      const blocks = groupCaptionsIntoBlocks(
        props.subtitles.captions,
        props.subtitles.maxChars || 20,
        props.subtitles.maxDurationMs || 2000
      );

      blocks.forEach((block, bIdx) => {
        const blockEl = document.createElement("div");
        blockEl.className = "subtitle-block";
        blockEl.id = `sub-block-${bIdx}`;
        blockEl.style.fontFamily = `'${fontFamily}', sans-serif`;
        blockEl.style.fontSize = `${fontSize}px`;
        blockEl.style.fontWeight = "800";
        blockEl.style.textTransform = isUppercase ? "uppercase" : "none";

        // RTL script check
        const isRtl = block.words.some((w) => RTL_CHARS.test(w.text));
        if (isRtl) {
          blockEl.setAttribute("dir", "rtl");
        }

        const blockStartSec = block.startMs / 1000;
        const blockEndSec = block.endMs / 1000;

        // Schedule block visibility
        tl.set(blockEl, { display: "block" }, blockStartSec);
        tl.set(blockEl, { display: "none" }, blockEndSec);

        // Word spans
        block.words.forEach((word, wIdx) => {
          if (wIdx > 0) {
            blockEl.appendChild(document.createTextNode(" "));
          }

          const wordSpan = document.createElement("span");
          wordSpan.className = "word-span";
          wordSpan.id = `word-${bIdx}-${wIdx}`;
          wordSpan.textContent = word.text;
          wordSpan.style.color = fontColor;
          wordSpan.style.opacity = `${baseOpacity}`;
          if (combinedTextShadow) {
            wordSpan.style.textShadow = combinedTextShadow;
          }

          if (reveal) {
            wordSpan.classList.add("hidden");
          }

          // Check semantic keyword highlights (Hormozi / MrBeast style)
          const cleanWord = word.text.toLowerCase().replace(/[^a-z0-9$]/g, "");
          const kwMatch = Array.isArray(props.keywordHighlights) &&
            props.keywordHighlights.find(k => k.word && cleanWord.includes(k.word.toLowerCase()));

          blockEl.appendChild(wordSpan);

          const wordStartSec = word.startMs / 1000;
          const wordEndSec = word.endMs / 1000;
          const wordDur = Math.max(0.05, wordEndSec - wordStartSec);

          // Reveal timing
          if (reveal) {
            tl.set(wordSpan, { visibility: "visible" }, wordStartSec);
          }

          // Semantic keyword highlight class
          if (kwMatch) {
            const semanticClass = `semantic-${kwMatch.color || "yellow"}`;
            tl.set(wordSpan, { className: `word-span ${semanticClass}` }, wordStartSec);
            tl.set(wordSpan, { className: "word-span" }, wordStartSec + wordDur);
          }

          // Active Word Animation
          if (animation === "pop") {
            tl.fromTo(wordSpan,
              { scale: 0.95, opacity: baseOpacity, color: fontColor },
              { scale: 1.15, opacity: 1.0, color: highlightColor, duration: 0.1, ease: "back.out(2)" },
              wordStartSec
            );
            tl.to(wordSpan, {
              scale: 1.0,
              opacity: baseOpacity,
              color: fontColor,
              duration: 0.1,
              ease: "power1.out"
            }, wordStartSec + wordDur);
          } else if (animation === "karaoke") {
            tl.to(wordSpan, {
              opacity: 1.0,
              color: highlightTextColor,
              backgroundColor: highlightColor,
              borderRadius: "6px",
              padding: "2px 10px",
              textShadow: "none",
              duration: 0.04
            }, wordStartSec);

            tl.to(wordSpan, {
              opacity: baseOpacity,
              color: fontColor,
              backgroundColor: "transparent",
              padding: "0px",
              textShadow: combinedTextShadow || "none",
              duration: 0.04
            }, wordStartSec + wordDur);
          } else if (animation === "word-highlight") {
            tl.to(wordSpan, {
              opacity: 1.0,
              color: highlightColor,
              textShadow: `0 0 16px ${highlightColor}, ${combinedTextShadow}`,
              duration: 0.05
            }, wordStartSec);

            tl.to(wordSpan, {
              opacity: baseOpacity,
              color: fontColor,
              textShadow: combinedTextShadow || "none",
              duration: 0.05
            }, wordStartSec + wordDur);
          } else {
            tl.to(wordSpan, { opacity: 1.0, color: highlightColor, duration: 0.05 }, wordStartSec);
            tl.to(wordSpan, { opacity: baseOpacity, color: fontColor, duration: 0.05 }, wordStartSec + wordDur);
          }
        });

        subContainer.appendChild(blockEl);
      });
    }

    // 7. Audio SFX Bus Layer (mapped for HyperFrames Producer multitrack mixer)
    const audioBus = document.getElementById("audio-bus");
    if (audioBus && Array.isArray(props.sfxTrack)) {
      audioBus.innerHTML = "";
      props.sfxTrack.forEach((sfx) => {
        const audioEl = document.createElement("audio");
        const sfxType = sfx.type || "whoosh";
        audioEl.src = `./audio/sfx/${sfxType}.mp3`;
        audioEl.setAttribute("data-start", `${sfx.startSec || 0}s`);
        audioEl.setAttribute("data-volume", `${sfx.volume != null ? sfx.volume : 0.8}`);
        audioEl.preload = "auto";
        audioBus.appendChild(audioEl);
      });
    }

    // Playhead seek function for external runners/testing
    window.seek = function (timeInSeconds) {
      tl.seek(timeInSeconds);
    };

    window.seekFrame = function (frameNumber) {
      tl.seek(frameNumber / fps);
    };

    console.log(`[HyperFrames] Initialized composition duration=${totalDurationSec.toFixed(2)}s (${durationInFrames} frames @ ${fps}fps)`);
    return tl;
  }

  // Expose globally
  window.initHyperFramesComposition = initHyperFramesComposition;
})();
