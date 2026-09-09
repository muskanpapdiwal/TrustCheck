/**
 * bg-network.js - animated "data network" canvas background.
 *
 * An original looping animation (not a video file): a field of drifting
 * dots that draw a thin connecting line to nearby neighbors, in the brand
 * blue at low opacity. Gives the "something alive is happening behind the
 * page" feel of a hero background video, fully self-contained (no asset
 * to host, no licensing concerns, tiny footprint).
 *
 * Respects prefers-reduced-motion: renders one static frame instead of
 * looping.
 */
(function () {
  var canvas = document.getElementById("bgCanvas");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");

  var PARTICLE_COUNT = 60;
  var MAX_LINK_DISTANCE = 130;
  var BRAND_RGB = "0, 71, 171"; // matches --brand: #0047ab

  var reduceMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var particles = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function initParticles() {
    particles = [];
    for (var i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.25,
        vy: (Math.random() - 0.5) * 0.25,
      });
    }
  }

  function step() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      if (!reduceMotion) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
      }
    }

    for (var i = 0; i < particles.length; i++) {
      for (var j = i + 1; j < particles.length; j++) {
        var a = particles[i], b = particles[j];
        var dx = a.x - b.x, dy = a.y - b.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MAX_LINK_DISTANCE) {
          var opacity = (1 - dist / MAX_LINK_DISTANCE) * 0.14;
          ctx.strokeStyle = "rgba(" + BRAND_RGB + ", " + opacity + ")";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }

    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      ctx.fillStyle = "rgba(" + BRAND_RGB + ", 0.3)";
      ctx.beginPath();
      ctx.arc(p.x, p.y, 1.8, 0, Math.PI * 2);
      ctx.fill();
    }

    if (!reduceMotion) requestAnimationFrame(step);
  }

  window.addEventListener("resize", function () {
    resize();
    initParticles();
  });

  resize();
  initParticles();
  step();
})();
