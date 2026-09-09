/**
 * bg-network.js - Subtle cybernetic particle constellation canvas background.
 *
 * An original lightweight ambient canvas mesh: floating micro-nodes with
 * proximity line rendering using indigo (#6366f1) and cyan (#06b6d4) hues
 * at low opacity. Designed for minimal CPU overhead.
 *
 * Respects prefers-reduced-motion.
 */
(function () {
  var canvas = document.getElementById("bgCanvas");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");

  var PARTICLE_COUNT = 48;
  var MAX_LINK_DISTANCE = 120;
  var COLOR_INDIGO = "99, 102, 241"; // #6366f1
  var COLOR_CYAN = "6, 182, 212";   // #06b6d4

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
      var isCyan = Math.random() > 0.65;
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        radius: Math.random() * 1.5 + 1,
        color: isCyan ? COLOR_CYAN : COLOR_INDIGO,
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

    // Connect close neighbors
    for (var i = 0; i < particles.length; i++) {
      for (var j = i + 1; j < particles.length; j++) {
        var a = particles[i], b = particles[j];
        var dx = a.x - b.x, dy = a.y - b.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MAX_LINK_DISTANCE) {
          var alpha = (1 - dist / MAX_LINK_DISTANCE) * 0.10;
          ctx.strokeStyle = "rgba(" + COLOR_INDIGO + ", " + alpha + ")";
          ctx.lineWidth = 0.85;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }

    // Render node points
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      ctx.fillStyle = "rgba(" + p.color + ", 0.35)";
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
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

