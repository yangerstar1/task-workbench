package com.desertrv.qa;

import android.app.Instrumentation;
import android.app.UiAutomation;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Base64;
import android.view.InputDevice;
import android.view.MotionEvent;
import org.json.JSONArray;
import org.json.JSONObject;

/** Independent self-targeting helper. Never links game code or changes game state directly. */
public final class TouchInstrumentation extends Instrumentation {
    private Bundle args;
    private long downTime, lastTime;
    private int events;
    @Override public void onCreate(Bundle a) { super.onCreate(a); args = a; start(); }
    private void inject(UiAutomation ui, int action, float[][] xy, int count) {
        MotionEvent.PointerProperties[] props = new MotionEvent.PointerProperties[count];
        MotionEvent.PointerCoords[] coords = new MotionEvent.PointerCoords[count];
        for (int i = 0; i < count; i++) {
            props[i] = new MotionEvent.PointerProperties(); props[i].id = i;
            props[i].toolType = MotionEvent.TOOL_TYPE_FINGER;
            coords[i] = new MotionEvent.PointerCoords(); coords[i].x = xy[i][0];
            coords[i].y = xy[i][1]; coords[i].pressure = 1; coords[i].size = 1;
        }
        // Wait for a genuinely later clock tick, rather than inventing future timestamps.
        long now; do { now = SystemClock.uptimeMillis(); if (now <= lastTime) SystemClock.sleep(1); } while (now <= lastTime);
        lastTime = now;
        MotionEvent e = MotionEvent.obtain(downTime, now, action, count, props, coords,
                0, 0, 1, 1, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
        try {
            if (!ui.injectInputEvent(e, true)) throw new AssertionError("Input injection rejected at event " + events);
            events++;
        } finally { e.recycle(); }
    }
    private float[][] frame(JSONArray a, int width, int height) throws Exception {
        if (a.length() != 2) throw new IllegalArgumentException("Exactly two fixed pointers required");
        float[][] xy = new float[2][2];
        for (int i=0;i<2;i++) {
            JSONArray p = a.getJSONArray(i);
            if (p.length()!=2) throw new IllegalArgumentException("Invalid point");
            xy[i][0]=(float)p.getDouble(0); xy[i][1]=(float)p.getDouble(1);
            if (!(xy[i][0]>=0 && xy[i][0]<width && xy[i][1]>=0 && xy[i][1]<height)) throw new IllegalArgumentException("Point out of screen");
        }
        return xy;
    }
    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            JSONObject plan = new JSONObject(new String(Base64.decode(args.getString("plan"), Base64.NO_WRAP), "UTF-8"));
            int width=plan.getInt("width"), height=plan.getInt("height");
            if ((width!=1280 && width!=1600) || height!=720) throw new IllegalArgumentException("Unreviewed screen size");
            JSONArray frames=plan.getJSONArray("frames");
            int interval=plan.getInt("intervalMs");
            if (frames.length()<2 || frames.length()>120 || interval<16 || interval>100) throw new IllegalArgumentException("Unbounded gesture");
            UiAutomation ui=getUiAutomation(UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES);
            float[][] xy=frame(frames.getJSONArray(0),width,height);
            downTime=SystemClock.uptimeMillis(); lastTime=downTime-1;
            inject(ui,MotionEvent.ACTION_DOWN,xy,1);
            inject(ui,MotionEvent.ACTION_POINTER_DOWN | (1 << MotionEvent.ACTION_POINTER_INDEX_SHIFT),xy,2);
            for(int i=1;i<frames.length();i++) {
                SystemClock.sleep(interval); xy=frame(frames.getJSONArray(i),width,height);
                inject(ui,MotionEvent.ACTION_MOVE,xy,2);
            }
            inject(ui,MotionEvent.ACTION_POINTER_UP | (1 << MotionEvent.ACTION_POINTER_INDEX_SHIFT),xy,2);
            inject(ui,MotionEvent.ACTION_UP,xy,1);
            result.putString("stream","QA_INPUT_OK events="+events+"; injection only, gameplay requires visual review\n");
            finish(-1,result);
        } catch (Throwable e) {
            result.putString("stream","QA_INPUT_FAILED: "+e.getClass().getSimpleName()+": "+e.getMessage()+"\n");
            finish(0,result);
        }
    }
}
