package com.mediadownloader.app

import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var platformSpinner: Spinner
    private lateinit var urlInput: EditText
    private lateinit var cookieInput: EditText
    private lateinit var output: TextView
    private lateinit var progress: ProgressBar

    private val platforms = listOf("douyin", "bilibili", "kuaishou", "xiaohongshu")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
        }

        root.addView(TextView(this).apply {
            text = "MediaDownloader"
            textSize = 22f
            gravity = Gravity.CENTER
        })

        root.addView(TextView(this).apply { text = "平台" })
        platformSpinner = Spinner(this).apply {
            adapter = ArrayAdapter(
                this@MainActivity,
                android.R.layout.simple_spinner_dropdown_item,
                platforms
            )
        }
        root.addView(platformSpinner)

        root.addView(TextView(this).apply { text = "Cookie (可选)" })
        cookieInput = EditText(this).apply {
            hint = "粘贴 Cookie 字符串"
            minLines = 2
        }
        root.addView(cookieInput)

        root.addView(TextView(this).apply { text = "作品链接" })
        urlInput = EditText(this).apply {
            hint = "粘贴作品链接 (抖音/快手/小红书/B站)"
            minLines = 2
        }
        root.addView(urlInput)

        val btnRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val parseBtn = Button(this).apply {
            text = "解析"
            setOnClickListener { runAsync("parse") }
        }
        val dlBtn = Button(this).apply {
            text = "下载"
            setOnClickListener { runAsync("download") }
        }
        val saveCookieBtn = Button(this).apply {
            text = "保存Cookie"
            setOnClickListener { runAsync("save_cookie") }
        }
        val lp = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        btnRow.addView(parseBtn, lp)
        btnRow.addView(dlBtn, lp)
        btnRow.addView(saveCookieBtn, lp)
        root.addView(btnRow)

        progress = ProgressBar(this).apply { visibility = View.GONE }
        root.addView(progress)

        output = TextView(this).apply {
            text = "就绪"
            setTextIsSelectable(true)
            textSize = 13f
        }
        root.addView(ScrollView(this).apply {
            addView(output)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
            )
        })

        setContentView(root)
    }

    private fun runAsync(action: String) {
        val url = urlInput.text.toString().trim()
        val cookie = cookieInput.text.toString().trim()
        val platform = platforms[platformSpinner.selectedItemPosition]

        if (action != "save_cookie" && url.isEmpty()) {
            output.text = "请输入链接"
            return
        }

        progress.visibility = View.VISIBLE
        output.text = "处理中..."

        Thread {
            val result = try {
                val py = Python.getInstance()
                val bridge = py.getModule("mediadownloader_bridge")
                when (action) {
                    "parse" -> bridge.callAttr("parse", url, platform).toString()
                    "download" -> bridge.callAttr("download", url, platform, "").toString()
                    "save_cookie" -> bridge.callAttr("set_cookie", platform, cookie).toString()
                    else -> """{"ok": false, "error": "未知操作"}"""
                }
            } catch (e: Exception) {
                """{"ok": false, "error": "${e.message?.replace("\"", "'")}"}"""
            }
            runOnUiThread {
                progress.visibility = View.GONE
                output.text = formatResult(result)
            }
        }.start()
    }

    private fun formatResult(json: String): String {
        return try {
            val o = JSONObject(json)
            if (o.optBoolean("ok", false)) {
                when {
                    o.has("work") -> {
                        val w = o.getJSONObject("work")
                        buildString {
                            appendLine("✓ 解析成功")
                            appendLine("标题: ${w.optString("title").take(60)}")
                            appendLine("作者: ${w.optString("author_name")}")
                            val imgs = w.optJSONArray("image_urls")?.length() ?: 0
                            appendLine("类型: ${if (w.optString("media_type") == "images") "图集 ($imgs 张)" else "视频"}")
                            appendLine("点赞: ${w.optString("digg_count")}  评论: ${w.optString("comment_count")}  播放: ${w.optString("view_count")}")
                            appendLine("链接: ${w.optString("share_url")}")
                        }
                    }
                    o.has("count") -> {
                        val files = o.optJSONArray("files")
                        buildString {
                            appendLine("✓ 下载完成 ${o.optInt("count")} 个文件")
                            if (files != null) {
                                for (i in 0 until files.length()) {
                                    appendLine("  ${files.getString(i)}")
                                }
                            }
                        }
                    }
                    o.has("cookie") -> {
                        val c = o.optString("cookie")
                        if (c.isNotEmpty()) "✓ 已保存 Cookie (${c.length} 字符)" else "✓ Cookie 已清除"
                    }
                    else -> "✓ 成功: $json"
                }
            } else {
                "✗ ${o.optString("error", "未知错误")}"
            }
        } catch (e: Exception) {
            json
        }
    }
}
