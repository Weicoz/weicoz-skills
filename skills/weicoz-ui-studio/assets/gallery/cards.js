(() => {
  const $ = (selector) => document.querySelector(selector);
  const all = (selector) => [...document.querySelectorAll(selector)];
  // 源码取初始 DOM，避免操作后状态污染可复用片段。
  all(".specimen").forEach((section) => {
    const details = document.createElement("details");
    details.className = "code-view";
    const summary = document.createElement("summary");
    summary.textContent = "查看 HTML 源码";
    const pre = document.createElement("pre");
    pre.textContent = section.querySelector(".card").outerHTML;
    details.append(summary, pre);
    section.append(details);
  });
  $("#filter")?.addEventListener("input", (event) => {
    let count = 0;
    all(".specimen").forEach((section) => {
      section.hidden = !section.dataset.name
        .toLowerCase()
        .includes(event.target.value.trim().toLowerCase());
      if (!section.hidden) count++;
    });
    $("#count").textContent = `${count} 个组件`;
    $("#no-matches").hidden = count !== 0;
  });
  $("#theme")?.addEventListener("change", (event) => {
    document.body.dataset.theme = event.target.value;
  });
  if ($("[data-action=bookmark]")) {
    $("[data-action=bookmark]").addEventListener("click", (event) => {
      const active = event.target.getAttribute("aria-pressed") !== "true";
      event.target.setAttribute("aria-pressed", active);
      event.target.textContent = active ? "已收藏" : "收藏";
    });
  }
  if ($("#quantity")) {
    let quantity = 1;
    function changeQuantity(amount) {
      quantity = Math.min(9, Math.max(1, quantity + amount));
      $("#quantity").value = quantity;
      $("#less").disabled = quantity === 1;
      $("#more").disabled = quantity === 9;
      $("#add").textContent = `加入 · ¥${128 * quantity}`;
      $("#cart-result").textContent = "";
    }
    $("#less").onclick = () => changeQuantity(-1);
    $("#more").onclick = () => changeQuantity(1);
    $("#add").onclick = () => {
      $("#cart-result").textContent =
        `已加入 ${quantity} 件，合计 ¥${128 * quantity}。`;
    };
  }
  if ($("#period")) {
    $("#period").onchange = (event) => {
      const month = event.target.value === "month";
      $("#metric-value").innerHTML = `${month ? 92 : 24}<span> 件</span>`;
      $("#metric-caption").textContent = month
        ? "较上月增加 18 件，按时交付率 95%。"
        : "较上周增加 6 件，按时交付率 96%。";
      $("#trend").setAttribute(
        "d",
        month
          ? "M0 72 L50 64 L100 39 L150 45 L200 22 L250 30 L300 4"
          : "M0 68 L50 54 L100 60 L150 32 L200 38 L250 18 L300 4",
      );
      $("#trend-title").textContent = month
        ? "本月交付逐步增加，共 92 件"
        : "本周交付从 2 件逐步增长到 6 件";
    };
  }
  if ($("#follow")) {
    $("#follow").onclick = (event) => {
      const active = event.target.getAttribute("aria-pressed") !== "true";
      event.target.setAttribute("aria-pressed", active);
      event.target.textContent = active ? "已关注" : "关注";
      $("#followers").textContent = `${active ? 129 : 128} 人关注`;
    };
  }
  if ($("#annual")) {
    $("#annual").onchange = (event) => {
      const year = event.target.checked;
      $("#price").textContent = year ? "¥288" : "¥30";
      $("#billing").textContent = year ? " / 年" : " / 月";
      $("#plan").textContent = year ? "选择年付" : "选择月付";
      $("#plan-result").textContent = "";
    };
    $("#plan").onclick = () => {
      $("#plan-result").textContent =
        `已选择${$("#annual").checked ? "年付 ¥288" : "月付 ¥30"}。`;
    };
  }
  all(".task-check").forEach(
    (input) =>
      (input.onchange = () => {
        const count = all(".task-check:checked").length;
        $("#task-progress").value = count;
        $("#task-result").textContent =
          count === 3 ? "3 / 3 全部完成" : `${count} / 3 已完成`;
      }),
  );
  if ($("#next-step")) {
    let step = 0;
    function updateStep() {
      all("#steps li").forEach((li, index) => {
        if (index === step) li.setAttribute("aria-current", "step");
        else li.removeAttribute("aria-current");
      });
      $("#next-step").disabled = step === 3;
      $("#step-result").textContent =
        step === 3
          ? "全部完成，祝阅读愉快。"
          : `当前：${all("#steps li")[step].textContent}`;
    }
    $("#next-step").onclick = () => {
      step = Math.min(3, step + 1);
      updateStep();
    };
    $("#reset-step").onclick = () => {
      step = 0;
      updateStep();
    };
  }
  if ($("#rsvp")) {
    $("#rsvp").onclick = (event) => {
      const active = event.target.getAttribute("aria-pressed") !== "true";
      event.target.setAttribute("aria-pressed", active);
      event.target.textContent = active ? "取消预留" : "预留座位";
      $("#seats").textContent = `还剩 ${active ? 7 : 8} 个座位`;
      $("#rsvp-result").textContent = active
        ? "已为你预留 1 个座位。"
        : "已取消，座位已归还。";
    };
  }
  if ($("#audio")) {
    const audio = $("#audio");
    $("#play").onclick = async () => {
      try {
        if (audio.paused) await audio.play();
        else audio.pause();
      } catch {
        $("#audio-result").textContent = "无法播放，请检查本地音频文件。";
      }
    };
    audio.addEventListener("play", () => {
      $("#play").textContent = "暂停";
      $("#audio-result").textContent = "正在播放";
    });
    audio.addEventListener("pause", () => {
      $("#play").textContent = "播放";
      $("#audio-result").textContent = audio.ended ? "已播放完毕" : "已暂停";
    });
    audio.addEventListener("ended", () => {
      $("#play").textContent = "重播";
      $("#audio-result").textContent = "已播放完毕";
    });
    audio.addEventListener("timeupdate", () => {
      $("#seek").value = Number.isFinite(audio.duration)
        ? (audio.currentTime / audio.duration) * 100
        : 0;
      $("#audio-time").value =
        `0:${Math.floor(audio.currentTime).toString().padStart(2, "0")}`;
    });
    $("#seek").oninput = (event) => {
      if (Number.isFinite(audio.duration))
        audio.currentTime = (audio.duration * event.target.value) / 100;
    };
  }
  if ($("#quote")) {
    const quotes = [
      ["终于可以把注意力放回作品本身。", "陈述 · 独立摄影师"],
      ["没有多余的东西，工作反而变得更顺畅。", "夏禾 · 内容编辑"],
      ["每天少找几次按钮，就多一点创作的时间。", "周岩 · 产品设计师"],
    ];
    let quote = 0;
    function quoteMove(delta) {
      quote = (quote + delta + quotes.length) % quotes.length;
      $("#quote").textContent = `“${quotes[quote][0]}”`;
      $("#quote-author").textContent = quotes[quote][1];
      $("#quote-page").value = `${quote + 1} / 3`;
    }
    $("#quote-prev").onclick = () => quoteMove(-1);
    $("#quote-next").onclick = () => quoteMove(1);
  }
  all("[data-trip]").forEach(
    (button) =>
      (button.onclick = () => {
        all("[data-trip]").forEach((item) =>
          item.setAttribute("aria-pressed", item === button),
        );
        $("#trip-result").textContent =
          `已选择${button.dataset.trip}：${button.dataset.trip === "山间" ? "适合安静地走一走。" : "迎着风，慢慢向前。"}`;
      }),
  );
  all(".read").forEach(
    (button) =>
      (button.onclick = () => {
        button.closest("li").dataset.read = "true";
        button.disabled = true;
        button.textContent = "已读";
        $("#unread").value = `${all(".read:not(:disabled)").length} 条未读`;
      }),
  );
  if ($("#inline-form")) {
    $("#inline-form").onsubmit = (event) => {
      event.preventDefault();
      const input = $("#project-name");
      input.value = input.value.trim();
      if (!input.reportValidity()) return;
      const button = event.target.querySelector("button");
      button.disabled = true;
      $("#inline-result").textContent = "正在保存…";
      setTimeout(() => {
        $("#inline-result").textContent = `已保存「${input.value}」。`;
        button.disabled = false;
      }, 250);
    };
  }
  if ($("#create-note")) {
    let notes = 0;
    $("#create-note").onclick = () => {
      notes++;
      const item = document.createElement("li");
      item.textContent = `新的想法 ${notes}`;
      $("#notes").append(item);
      $("#create-note").textContent = "再添一条";
    };
  }
  if ($("#advance")) {
    let kanban = 0;
    const kanbanStates = ["待开始", "进行中", "已完成"];
    $("#advance").onclick = (event) => {
      kanban = (kanban + 1) % 3;
      $("#kanban-state").textContent = kanbanStates[kanban];
      event.target.textContent = ["开始任务", "完成任务", "重新开始"][kanban];
    };
  }
  if ($("#fold-toggle")) {
    $("#fold-toggle").onclick = (event) => {
      const open = event.target.getAttribute("aria-expanded") !== "true";
      event.target.setAttribute("aria-expanded", open);
      event.target.textContent = open ? "收起信件" : "展开信件";
      $("#fold-body").hidden = !open;
    };
  }
  if ($("#drawer-toggle")) {
    function closeDrawer() {
      $("#drawer-body").hidden = true;
      $("#drawer-toggle").setAttribute("aria-expanded", "false");
      $("#drawer-toggle").focus();
    }
    $("#drawer-toggle").onclick = (event) => {
      const open = event.target.getAttribute("aria-expanded") !== "true";
      if (!open) {
        closeDrawer();
        return;
      }
      $("#drawer-text").value = $("#drawer-summary").textContent;
      $("#drawer-body").hidden = false;
      event.target.setAttribute("aria-expanded", "true");
      $("#drawer-text").focus();
    };
    $("#drawer-close").onclick = closeDrawer;
    $("#drawer-body").onkeydown = (event) => {
      if (event.key === "Escape") closeDrawer();
    };
    $("#drawer-form").onsubmit = (event) => {
      event.preventDefault();
      const input = $("#drawer-text");
      input.value = input.value.trim();
      if (!input.reportValidity()) return;
      $("#drawer-summary").textContent = input.value;
      $("#drawer-result").textContent = "介绍已保存。";
      closeDrawer();
    };
  }
  if ($(".spotlight")) {
    const spotlight = $(".spotlight");
    spotlight.onpointermove = (event) => {
      const box = spotlight.getBoundingClientRect();
      spotlight.style.setProperty(
        "--x",
        `${((event.clientX - box.left) / box.width) * 100}%`,
      );
      spotlight.style.setProperty(
        "--y",
        `${((event.clientY - box.top) / box.height) * 100}%`,
      );
    };
    $("#focus-start").onclick = (event) => {
      const active = event.target.textContent === "结束专注";
      event.target.textContent = active ? "开始专注" : "结束专注";
      $("#focus-result").textContent = active
        ? "休息一下，随时再回来。"
        : "这一刻，只留给眼前的任务。";
    };
  }
})();
