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
        public JourneyMotor motor;
        public Font font;
        RectTransform safe, menu;
        Text crosshair, hitMark;
        Image damageEdge;
        Text resources, objective, notice, prompt, menuTitle, menuBody, primaryLabel, storm;
        Button primary;
        Image playerBar, carBar, actionBar;
        readonly Dictionary<TouchControl, RectTransform> controls = new Dictionary<TouchControl, RectTransform>();
        Text interactLabel;
        RectTransform move, look;
        GameObject controlsRoot;
        readonly Vector3[] corners = new Vector3[4];
        Sprite rounded;
        readonly Color ink = new Color(.15f, .20f, .22f, .96f);
        readonly Color paper = new Color(.94f, .89f, .76f, .96f);
        readonly Color orange = new Color(.88f, .37f, .16f, 1);
        readonly Color pale = new Color(1, .95f, .84f, 1);

        void Awake()
        {
            rounded = RoundedSprite();
            var canvas = gameObject.AddComponent<Canvas>(); canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 20;
            var scaler = gameObject.AddComponent<CanvasScaler>(); scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1280, 720); scaler.matchWidthOrHeight = 1;
            gameObject.AddComponent<GraphicRaycaster>();
            if (!FindFirstObjectByType<EventSystem>())
            { var events = new GameObject("Journey UI events"); events.AddComponent<EventSystem>(); events.AddComponent<StandaloneInputModule>(); }
            safe = Rect("Safe area", transform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            var top = Panel("Vehicle status", safe, new Vector2(0, 1), new Vector2(0, 1), new Vector2(24, -24), new Vector2(260, 116), ink);
            Label("Journey label", top, "荒漠行路 / 01", 19, new Vector2(16, -10), new Vector2(228, 28), TextAnchor.UpperLeft);
            resources = Label("Resources", top, "", 21, new Vector2(16, -44), new Vector2(228, 56), TextAnchor.UpperLeft);
            playerBar = Progress(top, "Suit health", new Vector2(16, -106), new Vector2(100, 4), new Color(.74f,.82f,.64f));
            carBar = Progress(top, "RV condition", new Vector2(132, -106), new Vector2(112, 4), orange);
            var goal = Panel("Objective", safe, new Vector2(.5f, 1), new Vector2(.5f, 1), new Vector2(0, -24), new Vector2(510, 90), new Color(.15f,.20f,.22f,.85f));
            objective = Label("Objective text", goal, "", 24, new Vector2(18, -12), new Vector2(474, 65), TextAnchor.MiddleLeft);
            var pause = Button("Pause", safe, "II", new Vector2(1, 1), new Vector2(1, 1), new Vector2(-24, -24), new Vector2(76, 66), paper, ink);
            pause.onClick.AddListener(() => journey.TogglePause());
            storm = Label("Storm distance", safe, "", 20, Vector2.zero, new Vector2(230, 50), TextAnchor.MiddleRight);
            Anchor(storm.rectTransform, new Vector2(1, 1), new Vector2(1, 1), new Vector2(-120, -28), new Vector2(230, 50));
            var noticePanel = Panel("Notice", safe, new Vector2(.5f, 0), new Vector2(.5f, 0), new Vector2(0, 42), new Vector2(580, 78), new Color(.15f,.20f,.22f,.8f));
            notice = Label("Notice text", noticePanel, "", 23, new Vector2(20, -10), new Vector2(540, 60), TextAnchor.MiddleCenter);
            prompt = Label("World prompt", safe, "", 24, Vector2.zero, new Vector2(500, 46), TextAnchor.MiddleCenter);
            Anchor(prompt.rectTransform, new Vector2(.5f,.5f), new Vector2(.5f,.5f), new Vector2(0,-80), new Vector2(500,46));
            crosshair = Label("Aim", safe, "+", 26, Vector2.zero, new Vector2(38,38), TextAnchor.MiddleCenter);
            Anchor(crosshair.rectTransform,new Vector2(.5f,.5f),new Vector2(.5f,.5f),Vector2.zero,new Vector2(38,38));
            hitMark = Label("Hit confirmation",safe,"×",34,Vector2.zero,new Vector2(48,48),TextAnchor.MiddleCenter);
            Anchor(hitMark.rectTransform,new Vector2(.5f,.5f),new Vector2(.5f,.5f),Vector2.zero,new Vector2(48,48));
            damageEdge=Panel("Damage edge",safe,Vector2.zero,Vector2.zero,Vector2.zero,new Vector2(10,720),Color.clear).GetComponent<Image>();
            damageEdge.raycastTarget=false;
            actionBar = Progress(safe, "Action progress", new Vector2(0, -128), new Vector2(220, 7), orange);
            Anchor(actionBar.transform.parent.GetComponent<RectTransform>(), new Vector2(.5f,.5f), new Vector2(.5f,.5f), new Vector2(0,-128), new Vector2(220,7));
            controlsRoot = new GameObject("Touch controls", typeof(RectTransform)); controlsRoot.transform.SetParent(safe, false);
            Anchor(controlsRoot.GetComponent<RectTransform>(), Vector2.zero, Vector2.zero, Vector2.zero, Vector2.zero);
            // The look region is hit-test only. Actions are tested ahead of it.
            look = Rect("Look area", safe, new Vector2(.38f,0), Vector2.one, Vector2.zero, Vector2.zero);
            move = Control(TouchControl.Move, "移动", new Vector2(0,0), new Vector2(0,0), new Vector2(32,44), new Vector2(166,166), new Color(.15f,.20f,.22f,.65f));
            Control(TouchControl.Fire, "射击", Vector2.right, Vector2.right, new Vector2(-36,58), new Vector2(116,116), orange);
            Control(TouchControl.Reload, "装填", Vector2.right, Vector2.right, new Vector2(-50,192), new Vector2(96,76), ink);
            var interaction = Control(TouchControl.Interact, "下车", Vector2.right, Vector2.right, new Vector2(-184,70), new Vector2(132,96), paper);
            interactLabel = interaction.GetComponentInChildren<Text>(); interactLabel.color = ink;
            Control(TouchControl.Accelerate, "前进", Vector2.right, Vector2.right, new Vector2(-36,160), new Vector2(116,108), orange);
            Control(TouchControl.Brake, "制动\n倒车", Vector2.right, Vector2.right, new Vector2(-36,38), new Vector2(116,108), ink);
            menu = Panel("Menu", safe, new Vector2(.5f,.5f), new Vector2(.5f,.5f), Vector2.zero, new Vector2(600,380), ink);
            menuTitle = Label("Menu title", menu, "荒漠行路", 40, new Vector2(38,-32), new Vector2(524,65), TextAnchor.MiddleLeft);
            menuBody = Label("Menu description", menu, "", 25, new Vector2(38,-112), new Vector2(524,136), TextAnchor.UpperLeft);
            primary = Button("Menu action", menu, "出发", new Vector2(.5f,0), new Vector2(.5f,0), new Vector2(0,36), new Vector2(300,70), orange, pale);
            primaryLabel = primary.GetComponentInChildren<Text>();
            primary.onClick.AddListener(() =>
            {
                if (journey.State.Status == SessionStatus.Menu) station.Begin();
                else if (journey.State.Status == SessionStatus.Failed || journey.State.Status == SessionStatus.Completed) station.Restart();
                else if (journey.ManualPause) journey.TogglePause();
            });
        }
        void Update()
        {
            Rect area = Screen.safeArea;
            safe.anchorMin = new Vector2(area.xMin / Screen.width, area.yMin / Screen.height);
            safe.anchorMax = new Vector2(area.xMax / Screen.width, area.yMax / Screen.height);
            safe.offsetMin = safe.offsetMax = Vector2.zero;
            var state = journey.State;
            bool playing = state.Status == SessionStatus.Playing;
            bool driving = state.Control == ControlMode.Driving;
            resources.text = $"体力 {state.PlayerHealth}     车况 {state.VehicleHealth}\n钉弹 {state.LoadedAmmo} / {state.ReserveAmmo}  ·  修理包 {state.RepairKits}";
            playerBar.fillAmount = state.PlayerHealth / 100f; carBar.fillAmount = state.VehicleHealth / 300f;
            objective.text = station.Objective;
            notice.text = station.Notice;
            notice.transform.parent.gameObject.SetActive(!string.IsNullOrEmpty(station.Notice));
            crosshair.gameObject.SetActive(playing && !driving);
            hitMark.gameObject.SetActive(playing && station.HitConfirmation > 0);
            hitMark.color = orange;
            damageEdge.color = new Color(.8f,.12f,.05f,Mathf.Clamp01(station.DamageFeedback * 3));
            prompt.text = station.Installing ? "正在安装 · 移开会中断" : station.Reloading ? "正在装填钉条" : !driving ? station.Prompt : "";
            actionBar.transform.parent.gameObject.SetActive(station.ActionProgress > 0); actionBar.fillAmount = station.ActionProgress;
            storm.text = state.IsInStorm(station.WorldProgress) ? "风暴中 · 正在受伤" : "风暴正在逼近";
            foreach (var pair in controls)
            {
                bool show = playing && (pair.Key == TouchControl.Move || pair.Key == TouchControl.Interact ||
                    (driving ? pair.Key == TouchControl.Accelerate || pair.Key == TouchControl.Brake : pair.Key == TouchControl.Fire || pair.Key == TouchControl.Reload));
                pair.Value.gameObject.SetActive(show);
            }
            interactLabel.text = driving ? "下车" : string.IsNullOrEmpty(station.Prompt) ? "交互" : station.Prompt.Split('·')[0];
            menu.gameObject.SetActive(!playing);
            if (!playing)
            {
                bool dead = state.Status == SessionStatus.Failed;
                menuTitle.text = station.SliceComplete ? "第一站验证完成" : dead ? "旅程结束" : state.Status == SessionStatus.Menu ? "荒漠行路" : "旅程暂停";
                menuBody.text = station.SliceComplete ? "第一站到达出口，后续地区尚未接入。\n可返回站内继续检查，不能视为整局通关。" : dead ? "人和房车都得撑到最后。\n重新出发会重置本趟物资和改装。" : state.Status == SessionStatus.Menu ? "驾驶房车穿过荒漠，停车搜集，回车改装。\n先打通加油站；风暴从出发开始追赶。\n当前为第一站内部玩法验证版。" : "暂停时风暴与战斗一起冻结。";
                primaryLabel.text = dead ? "重新出发" : state.Status == SessionStatus.Menu ? "出发" : "继续";
                primary.interactable = state.Status == SessionStatus.Menu || dead || journey.ManualPause;
            }
            RegisterRegions();
        }
        void RegisterRegions()
        {
            var input = journey.Input; input.ClearRegions();
            if (journey.State.Status != SessionStatus.Playing) return;
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
            var image = rect.gameObject.AddComponent<Image>(); image.sprite = rounded; image.type = Image.Type.Sliced; image.color = color;
            return rect;
        }
        Text Label(string name, Transform parent, string value, int size, Vector2 pos, Vector2 bounds, TextAnchor alignment)
        {
            var rect=Rect(name,parent,new Vector2(0,1),new Vector2(0,1),pos,bounds); rect.pivot=new Vector2(0,1);
            var text=rect.gameObject.AddComponent<Text>(); text.font=font; text.text=value; text.fontSize=size; text.color=pale; text.alignment=alignment; text.raycastTarget=false;
            text.horizontalOverflow=HorizontalWrapMode.Wrap; text.verticalOverflow=VerticalWrapMode.Truncate;
            return text;
        }
        Button Button(string name, Transform parent,string label,Vector2 anchor,Vector2 pivot,Vector2 pos,Vector2 size,Color bg,Color fg)
        {
            var rect=Panel(name,parent,anchor,pivot,pos,size,bg); var button=rect.gameObject.AddComponent<Button>(); button.targetGraphic=rect.GetComponent<Image>();
            var text=Label("Label",rect,label,26,new Vector2(8,-8),size-new Vector2(16,16),TextAnchor.MiddleCenter);text.color=fg; return button;
        }
        Image Progress(Transform parent,string name,Vector2 pos,Vector2 size,Color color)
        {
            var track=Panel(name,parent,new Vector2(0,1),new Vector2(0,1),pos,size,new Color(0,0,0,.4f));
            var fill=Rect("Fill",track,Vector2.zero,Vector2.one,Vector2.zero,Vector2.zero).gameObject.AddComponent<Image>();
            fill.sprite=Sprite.Create(Texture2D.whiteTexture,new Rect(0,0,1,1),Vector2.one*.5f); fill.type=Image.Type.Filled;fill.fillMethod=Image.FillMethod.Horizontal;fill.color=color; return fill;
        }
        RectTransform Rect(string name,Transform parent,Vector2 min,Vector2 max,Vector2 pos,Vector2 size)
        { var r=new GameObject(name,typeof(RectTransform)).GetComponent<RectTransform>();r.SetParent(parent,false);r.anchorMin=min;r.anchorMax=max;r.anchoredPosition=pos;r.sizeDelta=size;return r; }
        void Anchor(RectTransform r,Vector2 anchor,Vector2 pivot,Vector2 pos,Vector2 size)
        {r.anchorMin=r.anchorMax=anchor;r.pivot=pivot;r.anchoredPosition=pos;r.sizeDelta=size;}
        Sprite RoundedSprite()
        {
            const int size=32;var tex=new Texture2D(size,size,TextureFormat.RGBA32,false);tex.filterMode=FilterMode.Bilinear;tex.wrapMode=TextureWrapMode.Clamp;
            for(int y=0;y<size;y++)for(int x=0;x<size;x++)
            {float dx=Mathf.Max(0,8-Mathf.Min(x,size-1-x)),dy=Mathf.Max(0,8-Mathf.Min(y,size-1-y));tex.SetPixel(x,y,new Color(1,1,1,Mathf.Clamp01(8.5f-Mathf.Sqrt(dx*dx+dy*dy))));}
            tex.Apply(); return Sprite.Create(tex,new Rect(0,0,size,size),Vector2.one*.5f,100,0,SpriteMeshType.FullRect,new Vector4(10,10,10,10));
        }
    }
}
