package org.thirdway.guideos.companion

import android.app.Activity
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Intent
import android.graphics.Typeface
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.Space
import android.widget.Switch
import android.widget.TextView
import org.thirdway.guideos.companion.events.EventPipeline
import org.thirdway.guideos.companion.notifications.DiscordNotificationListener

class MainActivity : Activity() {
    private lateinit var preferences: CompanionPreferences
    private lateinit var accessStatus: TextView
    private lateinit var forwardingSwitch: Switch
    private lateinit var queueStatus: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        preferences = CompanionPreferences(this)
        setContentView(ScrollView(this).apply { addView(buildInterface()) })
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    private fun buildInterface(): View {
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(24), dp(24), dp(24))
        }

        page.addView(text("GUIDE COMPANION", 24f, Typeface.BOLD))
        page.addView(text(
            "Lets this phone offer selected abilities to a Deck. Nothing is shared until you choose it.",
            16f,
        ).withTopMargin(8))

        page.addView(section("DISCORD MESSAGES"))
        accessStatus = text("", 16f)
        page.addView(accessStatus)

        page.addView(Button(this).apply {
            setText(R.string.choose_notification_access)
            isAllCaps = false
            setOnClickListener { startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }
        }.withTopMargin(12))

        forwardingSwitch = Switch(this).apply {
            setText(R.string.forward_discord)
            isChecked = preferences.discordForwardingEnabled
            setOnCheckedChangeListener { _, checked ->
                preferences.discordForwardingEnabled = checked
                refreshStatus()
            }
        }
        page.addView(forwardingSwitch.withTopMargin(16))

        page.addView(text("What may the Deck see?", 16f, Typeface.BOLD).withTopMargin(18))
        page.addView(RadioGroup(this).apply {
            orientation = RadioGroup.VERTICAL
            addPrivacyChoice("Sender only", PrivacyLevel.SENDER_ONLY)
            addPrivacyChoice("Sender and short preview", PrivacyLevel.SHORT_PREVIEW)
            addPrivacyChoice("Full notification text", PrivacyLevel.FULL_NOTIFICATION)
            setOnCheckedChangeListener { _, checkedId ->
                findViewById<RadioButton>(checkedId)?.tag?.let {
                    preferences.privacyLevel = it as PrivacyLevel
                }
            }
        })

        page.addView(section("DECK CONNECTION"))
        page.addView(text(EventPipeline.transport.state, 16f))
        page.addView(text(
            "Pairing is deliberately closed in this build. Captured events stay in temporary memory and disappear when the app stops.",
            14f,
        ).withTopMargin(8))

        queueStatus = text("", 14f)
        page.addView(queueStatus.withTopMargin(12))
        page.addView(Button(this).apply {
            setText(R.string.forget_events)
            isAllCaps = false
            setOnClickListener {
                EventPipeline.queue.clear()
                refreshStatus()
            }
        }.withTopMargin(8))

        page.addView(Space(this), LinearLayout.LayoutParams(1, dp(24)))
        page.addView(text(
            "Working build 0.1 — Discord notifications only. No message history, attachments, replies, contacts, microphone, or files.",
            13f,
        ))
        return page
    }

    private fun RadioGroup.addPrivacyChoice(label: String, level: PrivacyLevel) {
        addView(RadioButton(this@MainActivity).apply {
            id = View.generateViewId()
            tag = level
            text = label
            isChecked = preferences.privacyLevel == level
        })
    }

    private fun refreshStatus() {
        val hasAccess = hasNotificationAccess()
        accessStatus.text = if (hasAccess) {
            "Notification access: allowed"
        } else {
            "Notification access: not allowed"
        }
        forwardingSwitch.isEnabled = hasAccess
        queueStatus.text = getString(R.string.events_waiting, EventPipeline.queue.snapshot().size)
    }

    private fun hasNotificationAccess(): Boolean {
        val component = ComponentName(this, DiscordNotificationListener::class.java)
        return if (Build.VERSION.SDK_INT >= 27) {
            getSystemService(NotificationManager::class.java)
                .isNotificationListenerAccessGranted(component)
        } else {
            Settings.Secure.getString(contentResolver, "enabled_notification_listeners")
                ?.split(':')
                ?.any { ComponentName.unflattenFromString(it) == component } == true
        }
    }

    private fun section(value: String): TextView =
        text(value, 16f, Typeface.BOLD).withTopMargin(28) as TextView

    private fun text(value: String, size: Float, style: Int = Typeface.NORMAL) = TextView(this).apply {
        text = value
        textSize = size
        setTypeface(typeface, style)
    }

    private fun <T : View> T.withTopMargin(marginDp: Int): T {
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ).apply { topMargin = dp(marginDp) }
        return this
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
