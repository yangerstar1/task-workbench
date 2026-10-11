using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

namespace DesertRV
{
    public sealed class JourneyHud : MonoBehaviour
    {
        public JourneySession journey;
        public FirstStationJourney station;
        public JourneyDirector director;
        public JourneyMotor motor;
        public Font font;
        RectTransform safe, menu, statusPanel, objectivePanel, noticePanel, promptPanel, damagePanel, rearPanel;
        RectTransform menuShade, moveKnob, stormPanel;
        CanvasScaler scaler;
        Button pause;
        JourneyHudLayout layout;
        int layoutWidth, layoutHeight;
        Rect layoutSafeArea;
        float densityScale;
        public float PixelsPerLogicalUnit => densityScale;
        public string DensitySource { get; private set; }
        bool layoutKeyboard;
        Text crosshair, hitMark;
        Text damageDirection, rearThreat;
        Text regionLabel, playerResource, carResource, ammoResource, kitResource, objective, notice, prompt, menuTitle, menuBody, primaryLabel, storm;
        Button primary;
        Button keyboardLookToggle, keyboardLookSpeed;
        Text keyboardLookHelp;
        bool menuWasVisible;
        Image playerBar, carBar, actionBar;
        readonly Dictionary<TouchControl, RectTransform> controls = new Dictionary<TouchControl, RectTransform>();
        Text interactLabel;
        RectTransform move, look;
        
        readonly Vector3[] corners = new Vector3[4];
        Sprite rounded, circle, stickRing;
        readonly Color ink = new Color(.15f, .20f, .22f, .96f);
        readonly Color paper = new Color(.94f, .89f, .76f, .96f);
        readonly Color orange = new Color(.88f, .37f, .16f, 1);
        readonly Color pale = new Color(1, .95f, .84f, 1);

        void Awake()
        {
            rounded = RoundedSprite(); circle = CircleSprite(false); stickRing = CircleSprite(true);
            var canvas = gameObject.AddComponent<Canvas>(); canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 20;
            scaler = gameObject.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ConstantPixelSize;
            // Android uses logical display density, not physical DPI or a 720-height shrink.
            densityScale = ReadDisplayDensity();
            gameObject.AddComponent<GraphicRaycaster>();
            if (!FindFirstObjectByType<EventSystem>())
            { var events = new GameObject("Journey UI events"); events.transform.SetParent(transform, false); events.AddComponent<EventSystem>(); events.AddComponent<StandaloneInputModule>(); }
            safe = Rect("Safe area", transform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            var top = statusPanel = Panel("Vehicle status", safe, new Vector2(0, 1), new Vector2(0, 1), new Vector2(24, -24), new Vector2(280, 124), new Color(.15f,.20f,.22f,.82f));
            regionLabel = Label("Journey label", top, "荒漠行路 / 01", 19, new Vector2(16, -10), new Vector2(228, 28), TextAnchor.UpperLeft);
            playerResource = Label("Player health", top, "", 14, Vector2.zero, Vector2.zero, TextAnchor.MiddleLeft);
            carResource = Label("Vehicle health", top, "", 14, Vector2.zero, Vector2.zero, TextAnchor.MiddleLeft);
            ammoResource = Label("Ammunition", top, "", 14, Vector2.zero, Vector2.zero, TextAnchor.MiddleLeft);
            kitResource = Label("Repair kits", top, "", 14, Vector2.zero, Vector2.zero, TextAnchor.MiddleRight);
            playerBar = Progress(top, "Suit health", new Vector2(16, -114), new Vector2(100, 4), new Color(.74f,.82f,.64f));
            carBar = Progress(top, "RV condition", new Vector2(132, -114), new Vector2(132, 4), orange);
            var goal = objectivePanel = Panel("Objective", safe, new Vector2(.5f, 1), new Vector2(.5f, 1), new Vector2(0, -24), new Vector2(510, 90), new Color(.15f,.20f,.22f,.78f));
            objective = Label("Objective text", goal, "", 24, new Vector2(18, -12), new Vector2(474, 65), TextAnchor.MiddleLeft);
            pause = Button("Pause", safe, "II", new Vector2(1, 1), new Vector2(1, 1), new Vector2(-24, -24), new Vector2(76, 66), paper, ink);
            pause.onClick.AddListener(() => { if (!director || director.OwnsJourney) journey.TogglePause(); });
            stormPanel = Panel("Storm status", safe, Vector2.zero, Vector2.zero, Vector2.zero, Vector2.zero, new Color(.15f,.20f,.22f,.80f));
            storm = Label("Storm distance", stormPanel, "", 20, Vector2.zero, new Vector2(230, 50), TextAnchor.MiddleRight);
            Anchor(storm.rectTransform, new Vector2(1, 1), new Vector2(1, 1), new Vector2(-120, -28), new Vector2(230, 50));
            noticePanel = Panel("Notice", safe, new Vector2(.5f, 0), new Vector2(.5f, 0), new Vector2(0, 42), new Vector2(580, 78), new Color(.15f,.20f,.22f,.8f));
            notice = Label("Notice text", noticePanel, "", 23, new Vector2(20, -10), new Vector2(540, 60), TextAnchor.MiddleCenter);
            promptPanel = Panel("Action context", safe, Vector2.zero, Vector2.zero, Vector2.zero, Vector2.zero, new Color(.15f,.20f,.22f,.82f));
            prompt = Label("World prompt", promptPanel, "", 24, Vector2.zero, new Vector2(500, 46), TextAnchor.MiddleCenter);
            Anchor(prompt.rectTransform, new Vector2(.5f,.5f), new Vector2(.5f,.5f), new Vector2(0,-80), new Vector2(500,46));
            crosshair = Label("Aim", safe, "+", 26, Vector2.zero, new Vector2(38,38), TextAnchor.MiddleCenter);
            Anchor(crosshair.rectTransform,new Vector2(.5f,.5f),new Vector2(.5f,.5f),Vector2.zero,new Vector2(38,38));
            hitMark = Label("Hit confirmation",safe,"×",34,Vector2.zero,new Vector2(48,48),TextAnchor.MiddleCenter);
            Anchor(hitMark.rectTransform,new Vector2(.5f,.5f),new Vector2(.5f,.5f),Vector2.zero,new Vector2(48,48));
            damagePanel = Panel("Contact damage direction", safe, new Vector2(.5f,.5f), new Vector2(.5f,.5f),
                Vector2.zero, new Vector2(240,80), new Color(.15f,.08f,.05f,.80f));
            damagePanel.GetComponent<Image>().raycastTarget = false;
            damageDirection = Label("Damage direction text", damagePanel, "", 23, new Vector2(8,-4), new Vector2(224,72), TextAnchor.MiddleCenter);
            damageDirection.color = pale;
            rearPanel = Panel("Close rear threat", safe, new Vector2(.5f,.5f), new Vector2(.5f,.5f),
                new Vector2(0,105), new Vector2(380,40), new Color(.15f,.08f,.05f,.80f));
            rearPanel.GetComponent<Image>().raycastTarget = false;
            rearThreat = Label("Rear threat text", rearPanel, "", 22, new Vector2(8,-2), new Vector2(364,36), TextAnchor.MiddleCenter);
            rearThreat.color = pale;
            damagePanel.gameObject.SetActive(false); rearPanel.gameObject.SetActive(false);
            actionBar = Progress(safe, "Action progress", new Vector2(0, -128), new Vector2(220, 7), orange);
            Anchor(actionBar.transform.parent.GetComponent<RectTransform>(), new Vector2(.5f,.5f), new Vector2(.5f,.5f), new Vector2(0,-128), new Vector2(220,7));
            // The look region is hit-test only. Actions are tested ahead of it.
            look = Rect("Look area", safe, new Vector2(.38f,0), Vector2.one, Vector2.zero, Vector2.zero);
            move = Control(TouchControl.Move, "移动", new Vector2(0,0), new Vector2(0,0), new Vector2(32,44), new Vector2(166,166), new Color(.15f,.20f,.22f,.65f));
            Control(TouchControl.Fire, "射击", Vector2.right, Vector2.right, new Vector2(-36,58), new Vector2(116,116), orange);
            Control(TouchControl.Reload, "装填", Vector2.right, Vector2.right, new Vector2(-50,192), new Vector2(96,76), ink);
            var interaction = Control(TouchControl.Interact, "下车", Vector2.right, Vector2.right, new Vector2(-184,70), new Vector2(132,96), paper);
            interactLabel = interaction.GetComponentInChildren<Text>(); interactLabel.color = ink;
            Control(TouchControl.Accelerate, "前进", Vector2.right, Vector2.right, new Vector2(-36,160), new Vector2(116,108), orange);
            Control(TouchControl.Brake, "制动\n倒车", Vector2.right, Vector2.right, new Vector2(-36,38), new Vector2(116,108), ink);
            // The full overlay consumes menu taps; gameplay regions are cleared while open.
            menuShade = Rect("Menu shade", safe, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            var shade = menuShade.gameObject.AddComponent<Image>(); shade.color = new Color(.05f,.07f,.08f,.48f);
            menu = Panel("Menu", menuShade, new Vector2(.5f,.5f), new Vector2(.5f,.5f), Vector2.zero, new Vector2(600,380), ink);
            menuTitle = Label("Menu title", menu, "荒漠行路", 40, new Vector2(38,-32), new Vector2(524,65), TextAnchor.MiddleLeft);
            menuBody = Label("Menu description", menu, "", 25, new Vector2(38,-112), new Vector2(524,136), TextAnchor.UpperLeft);
            primary = Button("Menu action", menu, "出发", new Vector2(.5f,0), new Vector2(.5f,0), new Vector2(0,36), new Vector2(300,70), orange, pale);
            primaryLabel = primary.GetComponentInChildren<Text>();
            primary.onClick.AddListener(() =>
            {
                if (director && !director.OwnsJourney) return;
                if (director && director.CanRetryLoad) director.RetryLoad();
                else if (journey.State.Status == SessionStatus.Menu) { if (director) director.Begin(); else station.Begin(); }
                else if (journey.State.Status == SessionStatus.Failed || journey.State.Status == SessionStatus.Completed) { if (director) director.Restart(); else station.Restart(); }
                else if (journey.ManualPause) journey.TogglePause();
            });
            keyboardLookToggle = Button("Keyboard look mode", menu, "", new Vector2(.5f,0), new Vector2(.5f,0),
                new Vector2(-134,114), new Vector2(254,52), paper, ink);
            keyboardLookSpeed = Button("Keyboard look speed", menu, "", new Vector2(.5f,0), new Vector2(.5f,0),
                new Vector2(134,114), new Vector2(254,52), paper, ink);
            keyboardLookToggle.GetComponentInChildren<Text>().fontSize = 22;
            keyboardLookSpeed.GetComponentInChildren<Text>().fontSize = 22;
            keyboardLookHelp = Label("Keyboard look help", menu, "I/K 上下看 · J/L 左右转 · WASD/方向键移动", 18,
                new Vector2(38,-204), new Vector2(524,28), TextAnchor.MiddleLeft);
            keyboardLookToggle.onClick.AddListener(() => journey.Input.ConfigureKeyboardLook(
                !journey.Input.KeyboardLookEnabled, journey.Input.KeyboardLookSpeed));
            keyboardLookSpeed.onClick.AddListener(() =>
            {
                float speed = journey.Input.KeyboardLookSpeed;
                journey.Input.ConfigureKeyboardLook(journey.Input.KeyboardLookEnabled, speed < 60 ? 60 : speed < 120 ? 120 : 30);
            });
            keyboardLookToggle.navigation = new Navigation { mode = Navigation.Mode.Explicit,
                selectOnRight = keyboardLookSpeed, selectOnDown = primary, selectOnUp = primary };
            keyboardLookSpeed.navigation = new Navigation { mode = Navigation.Mode.Explicit,
                selectOnLeft = keyboardLookToggle, selectOnDown = primary, selectOnUp = primary };
            move.GetComponentInChildren<Text>().text = "";
            moveKnob = Panel("Stick thumb", move, new Vector2(.5f,.5f), new Vector2(.5f,.5f), Vector2.zero,
                new Vector2(30,30), new Color(.94f,.89f,.76f,.9f));
            move.GetComponent<Image>().sprite=stickRing; move.GetComponent<Image>().type=Image.Type.Simple;
            move.GetComponent<Image>().color=new Color(.94f,.89f,.76f,.72f);
            moveKnob.GetComponent<Image>().sprite=circle; moveKnob.GetComponent<Image>().type=Image.Type.Simple;
            foreach(var part in new[]{move,moveKnob})
            { var edge=part.gameObject.AddComponent<Outline>();edge.effectColor=ink;edge.effectDistance=new Vector2(1,-1); }
            foreach (var key in new[] {TouchControl.Fire,TouchControl.Accelerate,TouchControl.Brake})
            { controls[key].GetComponent<Image>().sprite=circle; controls[key].GetComponent<Image>().type=Image.Type.Simple; }
            controls[TouchControl.Fire].GetComponentInChildren<Text>().color=new Color(.07f,.09f,.10f);
            controls[TouchControl.Accelerate].GetComponentInChildren<Text>().color=new Color(.07f,.09f,.10f);
            primaryLabel.color=new Color(.07f,.09f,.10f);
            ApplyLayout(Screen.width, Screen.height, Screen.safeArea, !Application.isMobilePlatform);
        }
        void Update()
        {
            if (director && !director.OwnsJourney) { GetComponent<Canvas>().enabled = false; return; }
            var state = journey.State;
            regionLabel.text = $"荒漠行路 / {state.SceneId:00}";
            bool playing = state.Status == SessionStatus.Playing;
            bool driving = state.Control == ControlMode.Driving;
            playerResource.text = $"体力 {state.PlayerHealth}";
            carResource.text = $"车况 {state.VehicleHealth}";
            ammoResource.text = $"钉弹 {state.LoadedAmmo}/{state.ReserveAmmo}";
            kitResource.text = $"修理 {state.RepairKits}";
            playerBar.fillAmount = state.PlayerHealth / 100f; carBar.fillAmount = state.VehicleHealth / 300f;
            var actions = director ? director.actions : null;
            string currentPrompt = actions ? actions.Prompt : station.Prompt;
            bool installing = actions ? actions.Installing : station.Installing;
            bool reloading = actions ? actions.Reloading : station.Reloading;
            float progress = actions ? actions.ActionProgress : station.ActionProgress;
            objective.text = JourneyHudLayout.ObjectiveLines(director ? JourneyPresentation.Objective(state, director.Encounter) : station.Objective);
            notice.text = actions ? actions.Notice : station.Notice;
            noticePanel.gameObject.SetActive(playing && !string.IsNullOrEmpty(notice.text));
            crosshair.gameObject.SetActive(playing && !driving);
            hitMark.gameObject.SetActive(playing && (actions ? actions.HitConfirmation : station.HitConfirmation) > 0);
            hitMark.color = orange;
            bool contactDamage = motor && motor.DamageCueRemaining > 0;
            bool otherDamage = (actions ? actions.DamageFeedback : station.DamageFeedback) > 0;
            damageDirection.transform.parent.gameObject.SetActive(playing && (contactDamage || otherDamage));
            if (contactDamage)
            {
                Vector2 bearing = motor.DamageBearing;
                string direction = Mathf.Abs(bearing.x) > Mathf.Abs(bearing.y) ? (bearing.x > 0 ? "右侧" : "左侧") : (bearing.y >= 0 ? "前方" : "后方");
                damageDirection.text = $"{direction}受击 · {(motor.DamageToVehicle ? "车况" : "体力")} −{motor.DamageAmount}";
            }
            else damageDirection.text = "体力受损";
            var threat = playing && actions ? actions.CloseRearThreat : null;
            rearThreat.transform.parent.gameObject.SetActive(threat);
            bool inStorm=state.IsInStorm(director ? director.WorldProgress : station.WorldProgress);
            stormPanel.gameObject.SetActive(!threat);
            if (threat) rearThreat.text = (inStorm ? "风暴受伤 · " : "风暴逼近 · ") +
                (threat.Phase == BeastPhase.Windup ? "后方近敌蓄力" : threat.Phase == BeastPhase.Attack ? "后方近敌冲刺" : "后方近敌接近");
            prompt.text = installing ? "正在安装\n移开会中断" : reloading ? "正在装填钉条" : !driving ? JourneyHudLayout.PromptLines(currentPrompt) : "";
            promptPanel.gameObject.SetActive(playing && string.IsNullOrEmpty(notice.text) && !string.IsNullOrEmpty(prompt.text));
            actionBar.transform.parent.gameObject.SetActive(playing && progress > 0); actionBar.fillAmount = progress;
            storm.text = inStorm ? "风暴中 · 正在受伤" : "风暴正在逼近";
            foreach (var pair in controls)
            {
                bool show = playing && (pair.Key == TouchControl.Move || pair.Key == TouchControl.Interact ||
                    (driving ? pair.Key == TouchControl.Accelerate || pair.Key == TouchControl.Brake : pair.Key == TouchControl.Fire || pair.Key == TouchControl.Reload));
                pair.Value.gameObject.SetActive(show);
            }
            interactLabel.text = driving ? "下车" : actions ? actions.InteractionLabel : station.InteractionLabel;
            moveKnob.anchoredPosition = new Vector2(journey.Input.State.MoveX, journey.Input.State.MoveY) * (move.rect.width * .26f);
            menuShade.gameObject.SetActive(!playing);
            if (!playing)
            {
                bool dead = state.Status == SessionStatus.Failed;
                bool won = state.Status == SessionStatus.Completed;
                bool loading = state.Status == SessionStatus.Loading;
                bool slice = !director && station.SliceComplete;
                menuTitle.text = won ? "整局胜利" : loading ? "正在前往下一地区" : slice ? "第一站验证完成" : dead ? "旅程结束" : state.Status == SessionStatus.Menu ? "荒漠行路" : "旅程暂停";
                menuBody.text = won ? "信标已经完成，电缆已拔除，房车安全撤离。\n再次出发会重置整局资源与改装。" :
                    loading ? (director && director.CanRetryLoad ? director.LoadError : "正在加载地区，物资与风暴进度将保留。") :
                    slice ? "仅控制测试；不代表整局通关。" : dead ? "人和房车都得撑到最后。\n重新出发会重置本趟物资和改装。" :
                    state.Status == SessionStatus.Menu ? (director ? "驾驶、搜集、改装，穿过三个地区。\n风暴一直追赶；失败后从头出发。" : "第一站控制验证，战斗资产仍有门禁。") : "暂停时风暴与战斗一起冻结。";
                primaryLabel.text = director && director.CanRetryLoad ? "重试加载" : dead || won ? "整局重新出发" : state.Status == SessionStatus.Menu ? "出发" : "继续";
                primary.interactable = (director && director.CanRetryLoad) || state.Status == SessionStatus.Menu || dead || won || journey.ManualPause;
            }
            bool keyboardOptions = !Application.isMobilePlatform &&
                (state.Status == SessionStatus.Menu || state.Status == SessionStatus.Paused);
            keyboardLookToggle.gameObject.SetActive(keyboardOptions);
            keyboardLookSpeed.gameObject.SetActive(keyboardOptions);
            keyboardLookHelp.gameObject.SetActive(keyboardOptions);
            ApplyLayout(Screen.width, Screen.height, Screen.safeArea, keyboardOptions);
            if (keyboardOptions)
            {
                keyboardLookToggle.GetComponentInChildren<Text>().text = journey.Input.KeyboardLookEnabled ? "键盘视角：IJKL" : "键盘视角：关闭";
                keyboardLookSpeed.GetComponentInChildren<Text>().text = $"视角速度：{journey.Input.KeyboardLookSpeed:0}°/秒";
            }
            primary.navigation = new Navigation { mode = Navigation.Mode.Explicit,
                selectOnUp = keyboardOptions ? keyboardLookToggle : null,
                selectOnDown = keyboardOptions ? keyboardLookToggle : null };
            if (EventSystem.current && menuWasVisible != !playing)
                EventSystem.current.SetSelectedGameObject(!playing && primary.interactable ? primary.gameObject : null);
            menuWasVisible = !playing;
            RegisterRegions();
        }
#if UNITY_EDITOR
        // Renderer tests provide explicit simulated device metrics; shipping builds have no override.
        public void ConfigureLayoutPreview(int width, int height, Rect area, float pixelsPerUnit, bool keyboardOptions)
        {
            if (pixelsPerUnit <= 0) throw new System.ArgumentOutOfRangeException(nameof(pixelsPerUnit));
            layoutWidth=width; layoutHeight=height; densityScale=pixelsPerUnit; DensitySource="editor-simulated"; layout=null;
            ApplyLayout(width,height,area,keyboardOptions);
        }
#endif
        // Density is read on orientation/size changes, never for each label or each frame.
        float ReadDisplayDensity()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                using (var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
                using (var activity = player.GetStatic<AndroidJavaObject>("currentActivity"))
                using (var resources = activity.Call<AndroidJavaObject>("getResources"))
                using (var metrics = resources.Call<AndroidJavaObject>("getDisplayMetrics"))
                {
                    float density = metrics.Get<float>("density");
                    int displayWidth = metrics.Get<int>("widthPixels");
                    float scale=JourneyHudLayout.AndroidScale(density,Screen.width,displayWidth);
                    if (scale > 0) { DensitySource="android-display-metrics"; return scale; }
                    Debug.LogWarning("HUD display metrics were outside supported bounds; using unverified mobile fallback.");
                }
            }
            catch (System.Exception exception)
            { Debug.LogWarning("HUD display density unavailable: " + exception.GetType().Name); }
#endif
            // Unverified mobile fallback. Real device acceptance must record the density path.
            // It preserves the 360-unit mobile design rather than shrinking a desktop canvas.
            DensitySource=Application.isMobilePlatform ? "unverified-mobile-height-fallback" : "desktop-480-height";
            return Application.isMobilePlatform ? Mathf.Clamp(Screen.height / 360f,.75f,4f) : Mathf.Clamp(Screen.height / 480f,1f,4f);
        }
        void ApplyLayout(int width, int height, Rect area, bool keyboardOptions)
        {
            if (layout != null && layoutWidth == width && layoutHeight == height && layoutSafeArea == area && layoutKeyboard == keyboardOptions) return;
            if (layoutWidth != width || layoutHeight != height) densityScale = ReadDisplayDensity();
            layoutWidth = width; layoutHeight = height; layoutSafeArea = area; layoutKeyboard = keyboardOptions;
            scaler.scaleFactor = densityScale;
            safe.anchorMin = new Vector2(area.xMin / Mathf.Max(1,width), area.yMin / Mathf.Max(1,height));
            safe.anchorMax = new Vector2(area.xMax / Mathf.Max(1,width), area.yMax / Mathf.Max(1,height));
            safe.offsetMin = safe.offsetMax = Vector2.zero;
            layout = new JourneyHudLayout(area.size / densityScale, keyboardOptions);
            if (!layout.WithinSupportedEnvelope) Debug.LogWarning("HUD safe area is below the supported 568 x 296 logical-unit envelope; device validation required.");
            Place(statusPanel, layout.Status); Place(objectivePanel, layout.Objective);
            Place(pause.GetComponent<RectTransform>(), layout.Pause); FitLabel(pause.GetComponentInChildren<Text>(), 22, 4);
            Place(regionLabel.rectTransform, new Rect(8,2,158,20)); regionLabel.fontSize = 12;
            Place(playerResource.rectTransform, new Rect(8,23,76,22)); Place(carResource.rectTransform, new Rect(90,23,76,22));
            Place(playerBar.transform.parent.GetComponent<RectTransform>(), new Rect(8,47,76,4));
            Place(carBar.transform.parent.GetComponent<RectTransform>(), new Rect(90,47,76,4));
            Place(ammoResource.rectTransform, new Rect(8,53,110,24)); Place(kitResource.rectTransform, new Rect(118,53,48,24));
            FitLabel(objective, 16, 6);
            Place(stormPanel, layout.Storm); FitLabel(storm,14,4); storm.alignment=TextAnchor.MiddleLeft;
            Place(noticePanel, layout.Notice); FitLabel(notice, 14, 4);
            Place(promptPanel, layout.Prompt); FitLabel(prompt, 14, 4);
            Place(damagePanel, layout.Damage); FitLabel(damageDirection, 14, 4);
            Place(rearPanel, layout.RearThreat); FitLabel(rearThreat, 14, 4);
            Place(crosshair.rectTransform, layout.Aim); crosshair.fontSize=24;
            Place(hitMark.rectTransform, layout.Aim); hitMark.fontSize=28;
            Place(actionBar.transform.parent.GetComponent<RectTransform>(), layout.Progress);
            foreach (var pair in controls)
            {
                Place(pair.Value, layout.Control(pair.Key));
                FitLabel(pair.Value.GetComponentInChildren<Text>(), pair.Key == TouchControl.Reload ? 14 : 16, 4);
            }
            Anchor(menu, new Vector2(.5f,.5f), new Vector2(.5f,.5f), Vector2.zero, layout.Menu.size);
            Place(menuTitle.rectTransform, new Rect(24,12,layout.Menu.width-48,42)); menuTitle.fontSize=24;
            Place(menuBody.rectTransform, new Rect(24,62,layout.Menu.width-48,keyboardOptions ? 80 : 136)); menuBody.fontSize=16;
            Anchor(primary.GetComponent<RectTransform>(), new Vector2(.5f,0), new Vector2(.5f,0), new Vector2(0,16), new Vector2(180,52));
            FitLabel(primaryLabel, 16, 4);
            float optionWidth=(layout.Menu.width-56)*.5f;
            Place(keyboardLookToggle.GetComponent<RectTransform>(), new Rect(24,layout.Menu.height-128,optionWidth,48));
            Place(keyboardLookSpeed.GetComponent<RectTransform>(), new Rect(32+optionWidth,layout.Menu.height-128,optionWidth,48));
            FitLabel(keyboardLookToggle.GetComponentInChildren<Text>(), 14, 4); FitLabel(keyboardLookSpeed.GetComponentInChildren<Text>(), 14, 4);
            Place(keyboardLookHelp.rectTransform, new Rect(24,layout.Menu.height-174,layout.Menu.width-48,42)); keyboardLookHelp.fontSize=14;
        }
        static void Place(RectTransform rect, Rect box)
        {
            rect.anchorMin=rect.anchorMax=rect.pivot=new Vector2(0,1);
            rect.anchoredPosition=new Vector2(box.x,-box.y); rect.sizeDelta=box.size;
        }
        static void FitLabel(Text text, int size, float padding)
        {
            var r=text.rectTransform; r.anchorMin=Vector2.zero; r.anchorMax=Vector2.one; r.pivot=new Vector2(.5f,.5f);
            r.offsetMin=new Vector2(padding,1); r.offsetMax=new Vector2(-padding,-1); text.fontSize=size;
        }
        void RegisterRegions()
        {
            var input = journey.Input; input.ClearRegions();
            if (journey.State.Status != SessionStatus.Playing) return;
            input.SetUiBlocker(ScreenRect(pause.GetComponent<RectTransform>()));
            foreach (var pair in controls) if (pair.Value.gameObject.activeSelf) input.SetRegion(pair.Key, ScreenRect(pair.Value));
            if (journey.State.Control == ControlMode.OnFoot) input.SetRegion(TouchControl.Look, ScreenRect(look));
            input.StickRadius = ScreenRect(move).width * .42f;
        }
        Rect ScreenRect(RectTransform rect)
        { rect.GetWorldCorners(corners); return new Rect(corners[0].x,corners[0].y,corners[2].x-corners[0].x,corners[2].y-corners[0].y); }
        RectTransform Control(TouchControl key, string text, Vector2 anchor, Vector2 pivot, Vector2 pos, Vector2 size, Color color)
        {
            var rect = Panel(key.ToString(), safe, anchor, pivot, pos, size, color);
            Label("Label",rect,text,25,new Vector2(8,-8),size-new Vector2(16,16),TextAnchor.MiddleCenter);
            controls.Add(key, rect); return rect;
        }
        RectTransform Panel(string name, Transform parent, Vector2 anchor, Vector2 pivot, Vector2 pos, Vector2 size, Color color)
        {
            var rect = Rect(name,parent,anchor,anchor,pos,size); rect.pivot = pivot;
            var image = rect.gameObject.AddComponent<Image>(); image.raycastTarget = false; image.sprite = rounded; image.type = Image.Type.Sliced; image.color = color;
            return rect;
        }
        Text Label(string name, Transform parent, string value, int size, Vector2 pos, Vector2 bounds, TextAnchor alignment)
        {
            var rect=Rect(name,parent,new Vector2(0,1),new Vector2(0,1),pos,bounds); rect.pivot=new Vector2(0,1);
            var text=rect.gameObject.AddComponent<Text>(); text.font=font; text.text=value; text.fontSize=size; text.color=pale; text.alignment=alignment; text.raycastTarget=false;
            text.horizontalOverflow=HorizontalWrapMode.Wrap; text.verticalOverflow=VerticalWrapMode.Truncate; text.resizeTextForBestFit=false;
            return text;
        }
        Button Button(string name, Transform parent,string label,Vector2 anchor,Vector2 pivot,Vector2 pos,Vector2 size,Color bg,Color fg)
        {
            var rect=Panel(name,parent,anchor,pivot,pos,size,bg); var button=rect.gameObject.AddComponent<Button>(); button.targetGraphic=rect.GetComponent<Image>(); button.targetGraphic.raycastTarget=true;
            var text=Label("Label",rect,label,26,new Vector2(8,-8),size-new Vector2(16,16),TextAnchor.MiddleCenter);text.color=fg; return button;
        }
        Image Progress(Transform parent,string name,Vector2 pos,Vector2 size,Color color)
        {
            var track=Panel(name,parent,new Vector2(0,1),new Vector2(0,1),pos,size,new Color(0,0,0,.4f));
            var fill=Rect("Fill",track,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero).gameObject.AddComponent<Image>();
            fill.raycastTarget=false; fill.sprite=Sprite.Create(Texture2D.whiteTexture,new Rect(0,0,1,1),Vector2.one*.5f); fill.type=Image.Type.Filled;fill.fillMethod=Image.FillMethod.Horizontal;fill.color=color; return fill;
        }
        RectTransform Rect(string name,Transform parent,Vector2 min,Vector2 max,Vector2 pos,Vector2 size)
        { var r=new GameObject(name,typeof(RectTransform)).GetComponent<RectTransform>();r.SetParent(parent,false);r.anchorMin=min;r.anchorMax=max;r.anchoredPosition=pos;r.sizeDelta=size;return r; }
        void Anchor(RectTransform r,Vector2 anchor,Vector2 pivot,Vector2 pos,Vector2 size)
        {r.anchorMin=r.anchorMax=anchor;r.pivot=pivot;r.anchoredPosition=pos;r.sizeDelta=size;}
        void OnDestroy()
        {
            foreach (var generated in new[] {rounded,circle,stickRing})
                if (generated) { DisposeGenerated(generated.texture); DisposeGenerated(generated); }
            foreach (var bar in new[] {playerBar,carBar,actionBar}) if (bar && bar.sprite) DisposeGenerated(bar.sprite);
        }
        static void DisposeGenerated(Object item)
        { if (Application.isPlaying) Destroy(item); else DestroyImmediate(item); }
        Sprite CircleSprite(bool ring)
        {
            const int size=64; var texture=new Texture2D(size,size,TextureFormat.RGBA32,false);
            texture.filterMode=FilterMode.Bilinear; texture.wrapMode=TextureWrapMode.Clamp;
            for(int y=0;y<size;y++) for(int x=0;x<size;x++)
            {
                float distance=Vector2.Distance(new Vector2(x+.5f,y+.5f),new Vector2(32,32));
                float alpha=Mathf.Clamp01(31.5f-distance);
                if(ring) alpha*=Mathf.Clamp01(distance-27.5f);
                texture.SetPixel(x,y,new Color(1,1,1,alpha));
            }
            texture.Apply(); return Sprite.Create(texture,new Rect(0,0,size,size),Vector2.one*.5f);
        }
        Sprite RoundedSprite()
        {
            const int size=32;var tex=new Texture2D(size,size,TextureFormat.RGBA32,false);tex.filterMode=FilterMode.Bilinear;tex.wrapMode=TextureWrapMode.Clamp;
            for(int y=0;y<size;y++)for(int x=0;x<size;x++)
            {float dx=Mathf.Max(0,8-Mathf.Min(x,size-1-x)),dy=Mathf.Max(0,8-Mathf.Min(y,size-1-y));tex.SetPixel(x,y,new Color(1,1,1,Mathf.Clamp01(8.5f-Mathf.Sqrt(dx*dx+dy*dy))));}
            tex.Apply(); return Sprite.Create(tex,new Rect(0,0,size,size),Vector2.one*.5f,100,0,SpriteMeshType.FullRect,new Vector4(10,10,10,10));
        }
    }
}
