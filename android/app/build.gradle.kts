// MediaDownloader Android — app 模块 (Chaquopy 嵌入 CPython, 复用仓库根 shared/ + platforms/)
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// 把仓库根的 shared/ 与 platforms/ 复制为顶层 Python 包 (与桌面端 import 路径一致)
val generatedPythonSrc = layout.buildDirectory.dir("generated/python-src")

val copyPythonSources = tasks.register<Copy>("copyPythonSources") {
    description = "复制 shared/ 与 platforms/ 供 Chaquopy 打包"
    from(layout.projectDirectory.dir("../../shared")) { into("shared") }
    from(layout.projectDirectory.dir("../../platforms")) { into("platforms") }
    into(generatedPythonSrc)
    exclude("**/__pycache__/**", "**/*.pyc", "**/*.pyo")
}

tasks.configureEach {
    if (name.contains("Python") || name.contains("python")) {
        dependsOn(copyPythonSources)
    }
}

android {
    namespace = "com.mediadownloader.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.mediadownloader.app"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }

        python {
            version = "3.11"
            // pip 依赖: 与 requirements.txt 对齐 (PySide6/pyperclip 为桌面专用, 不打包)
            pip {
                install("aiofiles")
                install("curl-cffi")
                install("lxml")
                install("Pillow")
                install("qrcode[pil]")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    sourceSets.getByName("main") {
        python.srcDirs(
            "src/main/python",
            generatedPythonSrc.get().asFile.absolutePath,
        )
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
}
