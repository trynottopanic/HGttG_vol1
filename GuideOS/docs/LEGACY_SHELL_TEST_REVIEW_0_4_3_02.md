# Shell failure review: 0.4.3.02

3 October 2026. Review against current working source and the retained release
gate log: 209 shell tests, 35 failures and 32 errors. No production code, original
tests, baseline identities, signed candidate or Seed was changed by this review.
The existing signed image remains the pre-review candidate. Source/host probes
are not installed-image or physical evidence.

## Finding requiring a code fix

**High priority: a removed Wi-Fi row can crash shell context confirmation.**
The current production Screen was bound to a ShellState, the Wi-Fi panel opened
through its current Settings route, and the original stale-popup test executed.
After the selected network disappeared, confirmation reached
`MenuInput.context_action()` and `activate()`. The rendered target still existed,
but `activate()` searched current Wi-Fi rows using an unchecked `next(...)`.
It raised `StopIteration` at `guide_menu_input.py:317`.

This is a valid stale-input/integrity requirement from MENU_POINTER_0.md: provider
refresh must not redirect a captured context action to another network. Reject
the missing target, close/invalidate the popup, request redraw, and preserve the
remaining selection. Check both disappearance and connect/disconnect identity
changes against actual rendered regions. Do not merely add this identity to the
pre-existing-failure baseline. No fix was applied during the review itself;
the authorized deployment follow-up below records the subsequent correction.

## Review groups

### Authorized deployment follow-up

After this review, the owner authorized writing the connected Seed. The missing
Wi-Fi-row lookup is now checked before activation; rejection clears input focus
and requests redraw. Detail activation also rejects a captured Connect target
that has become Disconnect. Two new tests exercise current rendered targets
with changed provider state and passed. The shell suite now runs 211 tests with
the same 35 failures and 32 errors and no new failing identities. Those legacy
test repairs remain separate work. A new image is rebased from the fresh
3 October Seed capture for the authorized deployment; the original reviewed
image above remains retained.

**G1 — feature-profile and import-order fixture errors.** Tests set environment
variables around importing an already cached shell module; feature flags were
fixed earlier at module import. They then unconditionally register
`state.operations.close`, although operations is None. Rerunning the r8 module
alone eliminated all these setup errors: 13 tests ran, with six assertion
failures. Those residual assertions include old Audio-test routing, assumed
initial hidden tray, a generic grid forced onto Home, and B sent directly to
the private `_key` handler. Public `ShellState.key` owns the audio B return path;
the private call bypasses it. Tests must explicitly construct their feature
profile and exercise public input. Two update-notice tests have the same cached
feature-flag defect and still need isolated reruns after setup repair.

**G2 — incomplete shell-loop doubles.** Generic Screen mocks fail at
`screen.statusbar.volume_frame > 0` before hardware input is processed. The
privacy assertion consequently sees TypeError rather than the injected
ValueError. Correcting status-bar poll/volume and framebuffer last_metrics in a
review-only probe made the privacy exception test pass, including secret-free
report/traceback and draft cleanup. Power-off/report-failure, pointer report
frequency, input-frame ordering and Wi-Fi shutdown tests also retain old menu
event sequences and require replacement with current bounded public routes;
their guarantees are not established by the original failing tests.

**G3 — retired Field Home layout.** The spatial suite patches old PAGES/CHOICES,
expects ten-item Home pages, and calls removed Screen._field_layout. Current Home
uses the three-sector wheel, four-slot tray and world button. Current L2/R2
scroll the wheel. Generic content paging and power confirmation remain valid
requirements; move their tests to actual non-Home layouts/current Power entry.
Do not resurrect the retired Home renderer just to satisfy these assertions.

**G4 — original vertical Home menu.** Initial Debian tests manipulate selection
and PAGES to launch status, Wi-Fi or Power. Public input now addresses HomeState
instead. Retain repeat suppression, explicit power confirmation and cancelled
scan requirements, but rewrite entry through current visible controls.

**G5 — changed Home defaults, regions and file-detail presentation.** The tray
starts extended; tests assume hidden, then toggle it and expect extension.
HomeState.update returns redraw for its 10fps world frame, so an assertion that
R3 yields exactly (False, None) does not prove an R3 action occurred. Rendering
now includes world and tray hit regions. File details use fixed full-width rows;
the old no-action fixture compares two intentionally identical images instead
of checking valid geometry and action gating. Replace these assertions with
semantic controls, tray direction/timing from both starting states, and current
visible content/regions. The source comment reserving R3 and the older concept
document assigning R3 tray-toggle conflict; resolve that documentation explicitly
before treating either historical expectation as authoritative.

**G6 — menu/pointer/context fixtures and coverage gaps.** Old Home targets are
mixed with current Home focus identities, preventing most tests from reaching
Wi-Fi. A review-only current-route/pointer-mode correction passed 12 of 15
targeted cases, including privacy and eleven Wi-Fi context/keyboard cases. Three
remained: busy-task initial focus, D-pad focus after reorder, and pointer hit
identity after reorder. The current renderer was then bound: 6 of 15 passed;
old row geometry/labels and focus assumptions caused additional mismatches, and
the stale-confirmation crash above was exposed. These are diagnostic probes,
not replacement acceptance tests. The implementation's independent pointer
policy conflicts with MENU_POINTER_0.md's D-pad cursor-sync wording; review the
current intended contract and test stable action identity separately from
pointer coordinates. Busy-task cancel focus needs current-rendered acceptance,
not an assertion that an unhovered pointer necessarily makes A inert.

## Required follow-up

1. Fix and regression-test missing/stale Wi-Fi action activation through the
   public shell and production renderer before installation of this candidate.
2. Make feature flags, worker teardown and display doubles explicit and isolated.
   Re-run the blocked power/privacy/order/report tests with current input routes.
3. Replace retired Home/layout expectations while preserving test intent. Add
   current geometry checks for network reorder and busy-task cancellation.
4. Resolve pointer-sync and R3 documentation conflicts. Rerun all shell checks
   and update the baseline only for deliberate retired behavior, with evidence.
5. Rebuild/verify the image after production changes. This review has not made
   the legacy suite green and does not establish Deck acceptance.

Evidence is under build/release-0.4.3.02/: legacy-review-r8-isolated.log,
legacy-review-r8-media-profile.log, legacy-review-probes.json and
legacy-review-rendered-probes.json. review-legacy-probes.py changes only review
fixtures; original test files remain unchanged. legacy-failure-review.json
records every original occurrence and the retained test-log hash.

## Complete original failure/error ledger

Occurrence counts include subtests: 35 failures and 32 errors. They are not 67 independent defects.

| Group | Occurrences |
| --- | ---: |
| G1 | 20 |
| G2 | 5 |
| G3 | 8 |
| G4 | 5 |
| G5 | 5 |
| G6 | 24 |

| # | Original result | Test / subtest | Review group |
| --- | --- | --- | --- |
| 1 | ERROR | `test_report_failure_does_not_suppress_confirmed_power_request (test_guide_shell.ReportFailureTests.test_report_failure_does_not_suppress_confirmed_power_request)` | G2 |
| 2 | ERROR | `test_audio_settings_is_one_test_button (test_r8_navigation.SettingsRegressionTests.test_audio_settings_is_one_test_button)` | G1 |
| 3 | ERROR | `test_board_start_code_is_treated_as_physical_select_on_home (test_r8_navigation.SettingsRegressionTests.test_board_start_code_is_treated_as_physical_select_on_home)` | G1 |
| 4 | ERROR | `test_cursor_position_survives_navigation_and_dpad_focus (test_r8_navigation.SettingsRegressionTests.test_cursor_position_survives_navigation_and_dpad_focus)` | G1 |
| 5 | ERROR | `test_every_available_settings_child_returns_to_settings (test_r8_navigation.SettingsRegressionTests.test_every_available_settings_child_returns_to_settings) (setting='audio')` | G1 |
| 6 | ERROR | `test_every_available_settings_child_returns_to_settings (test_r8_navigation.SettingsRegressionTests.test_every_available_settings_child_returns_to_settings) (setting='connections')` | G1 |
| 7 | ERROR | `test_every_available_settings_child_returns_to_settings (test_r8_navigation.SettingsRegressionTests.test_every_available_settings_child_returns_to_settings) (setting='storage')` | G1 |
| 8 | ERROR | `test_every_available_settings_child_returns_to_settings (test_r8_navigation.SettingsRegressionTests.test_every_available_settings_child_returns_to_settings) (setting='power')` | G1 |
| 9 | ERROR | `test_every_available_settings_child_returns_to_settings (test_r8_navigation.SettingsRegressionTests.test_every_available_settings_child_returns_to_settings) (setting='updates')` | G1 |
| 10 | ERROR | `test_every_available_settings_child_returns_to_settings (test_r8_navigation.SettingsRegressionTests.test_every_available_settings_child_returns_to_settings) (setting='diagnostics')` | G1 |
| 11 | ERROR | `test_every_available_settings_child_returns_to_settings (test_r8_navigation.SettingsRegressionTests.test_every_available_settings_child_returns_to_settings) (setting='about')` | G1 |
| 12 | ERROR | `test_every_settings_focus_has_a_valid_identity (test_r8_navigation.SettingsRegressionTests.test_every_settings_focus_has_a_valid_identity)` | G1 |
| 13 | ERROR | `test_generic_two_column_grid_moves_relative_to_selection (test_r8_navigation.SettingsRegressionTests.test_generic_two_column_grid_moves_relative_to_selection)` | G1 |
| 14 | ERROR | `test_internal_wifi_back_precedes_parent_back (test_r8_navigation.SettingsRegressionTests.test_internal_wifi_back_precedes_parent_back)` | G1 |
| 15 | ERROR | `test_menu_clears_hierarchy_and_returns_home (test_r8_navigation.SettingsRegressionTests.test_menu_clears_hierarchy_and_returns_home)` | G1 |
| 16 | ERROR | `test_menu_code_is_treated_as_physical_select_on_home (test_r8_navigation.SettingsRegressionTests.test_menu_code_is_treated_as_physical_select_on_home)` | G1 |
| 17 | ERROR | `test_select_toggles_home_tray_and_r3_does_not (test_r8_navigation.SettingsRegressionTests.test_select_toggles_home_tray_and_r3_does_not)` | G1 |
| 18 | ERROR | `test_settings_child_b_returns_to_settings_then_home (test_r8_navigation.SettingsRegressionTests.test_settings_child_b_returns_to_settings_then_home)` | G1 |
| 19 | ERROR | `test_settings_down_reaches_about_without_exception (test_r8_navigation.SettingsRegressionTests.test_settings_down_reaches_about_without_exception)` | G1 |
| 20 | ERROR | `test_horizontal_transition_and_selection_guard (test_spatial_navigation.SpatialNavigationTests.test_horizontal_transition_and_selection_guard)` | G3 |
| 21 | ERROR | `test_pointer_cancel_and_back_still_work (test_spatial_navigation.SpatialNavigationTests.test_pointer_cancel_and_back_still_work)` | G3 |
| 22 | ERROR | `test_left_cursor_and_primary_click_use_hovered_target (test_stick_integration.MenuIntegrationTests.test_left_cursor_and_primary_click_use_hovered_target) (button=305)` | G6 |
| 23 | ERROR | `test_left_cursor_and_primary_click_use_hovered_target (test_stick_integration.MenuIntegrationTests.test_left_cursor_and_primary_click_use_hovered_target) (button=317)` | G6 |
| 24 | ERROR | `test_pointer_redraws_do_not_repeatedly_persist_unchanged_home_view (test_stick_integration.MenuIntegrationTests.test_pointer_redraws_do_not_repeatedly_persist_unchanged_home_view)` | G2 |
| 25 | ERROR | `test_primary_click_selects_context_wedge_without_underlying_fallthrough (test_stick_integration.MenuIntegrationTests.test_primary_click_selects_context_wedge_without_underlying_fallthrough) (button=305)` | G6 |
| 26 | ERROR | `test_primary_click_selects_context_wedge_without_underlying_fallthrough (test_stick_integration.MenuIntegrationTests.test_primary_click_selects_context_wedge_without_underlying_fallthrough) (button=317)` | G6 |
| 27 | ERROR | `test_right_stick_highlights_while_held_and_confirms_once_on_release (test_stick_integration.MenuIntegrationTests.test_right_stick_highlights_while_held_and_confirms_once_on_release)` | G6 |
| 28 | ERROR | `test_cached_menu_matches_full_render_and_does_not_repaint_static_text (test_stick_integration.RenderingCostTests.test_cached_menu_matches_full_render_and_does_not_repaint_static_text)` | G6 |
| 29 | ERROR | `test_shell_preserves_fast_frame_order_and_excludes_axes_from_reports (test_stick_integration.StickIntegrationTests.test_shell_preserves_fast_frame_order_and_excludes_axes_from_reports)` | G2 |
| 30 | ERROR | `test_home_a_acknowledges_ready_update_notice (test_v3_ui.V3RenderTests.test_home_a_acknowledges_ready_update_notice)` | G1 |
| 31 | ERROR | `test_settings_updates_opens_real_updates_panel (test_v3_ui.V3RenderTests.test_settings_updates_opens_real_updates_panel)` | G1 |
| 32 | ERROR | `test_shell_excludes_wifi_keystrokes_from_reports_and_still_shuts_down (test_wifi_panel.PanelTests.test_shell_excludes_wifi_keystrokes_from_reports_and_still_shuts_down)` | G2 |
| 33 | FAIL | `test_baseline_profile_maps_third_choice_to_power (test_guide_shell.StateTests.test_baseline_profile_maps_third_choice_to_power)` | G4 |
| 34 | FAIL | `test_menu_navigation_and_pages (test_guide_shell.StateTests.test_menu_navigation_and_pages)` | G4 |
| 35 | FAIL | `test_power_requires_separate_confirmation (test_guide_shell.StateTests.test_power_requires_separate_confirmation)` | G4 |
| 36 | FAIL | `test_repeat_and_release_do_not_replay (test_guide_shell.StateTests.test_repeat_and_release_do_not_replay)` | G4 |
| 37 | FAIL | `test_wifi_scan_is_cancellable_and_does_not_connect (test_guide_shell.StateTests.test_wifi_scan_is_cancellable_and_does_not_connect)` | G4 |
| 38 | FAIL | `test_edges_and_empty_cells_do_not_wrap (test_spatial_navigation.SpatialNavigationTests.test_edges_and_empty_cells_do_not_wrap)` | G3 |
| 39 | FAIL | `test_grid_moves_in_all_four_directions (test_spatial_navigation.SpatialNavigationTests.test_grid_moves_in_all_four_directions)` | G3 |
| 40 | FAIL | `test_paged_grid_dpad_and_activation_use_global_option_identity (test_spatial_navigation.SpatialNavigationTests.test_paged_grid_dpad_and_activation_use_global_option_identity)` | G3 |
| 41 | FAIL | `test_power_cancel_is_visible_and_does_not_shutdown (test_spatial_navigation.SpatialNavigationTests.test_power_cancel_is_visible_and_does_not_shutdown)` | G3 |
| 42 | FAIL | `test_trigger_pages_keep_slot_and_clamp_partial_last_page (test_spatial_navigation.SpatialNavigationTests.test_trigger_pages_keep_slot_and_clamp_partial_last_page)` | G3 |
| 43 | FAIL | `test_triggers_leave_single_page_unchanged (test_spatial_navigation.SpatialNavigationTests.test_triggers_leave_single_page_unchanged)` | G3 |
| 44 | FAIL | `test_back_and_menu_cancel_context_without_activating_underlying_network (test_stick_integration.MenuIntegrationTests.test_back_and_menu_cancel_context_without_activating_underlying_network)` | G6 |
| 45 | FAIL | `test_busy_page_initial_cursor_does_not_cancel_but_dpad_can_focus_cancel (test_stick_integration.MenuIntegrationTests.test_busy_page_initial_cursor_does_not_cancel_but_dpad_can_focus_cancel)` | G6 |
| 46 | FAIL | `test_captured_connect_action_cannot_turn_into_disconnect_before_refresh_sync (test_stick_integration.MenuIntegrationTests.test_captured_connect_action_cannot_turn_into_disconnect_before_refresh_sync)` | G6 |
| 47 | FAIL | `test_context_back_home_and_close_directions_have_separate_effects (test_stick_integration.MenuIntegrationTests.test_context_back_home_and_close_directions_have_separate_effects)` | G6 |
| 48 | FAIL | `test_context_direct_connect_uses_captured_network_and_does_not_retarget (test_stick_integration.MenuIntegrationTests.test_context_direct_connect_uses_captured_network_and_does_not_retarget)` | G6 |
| 49 | FAIL | `test_context_expands_and_filters_unavailable_or_unsaved_network_actions (test_stick_integration.MenuIntegrationTests.test_context_expands_and_filters_unavailable_or_unsaved_network_actions)` | G6 |
| 50 | FAIL | `test_context_target_survives_network_reordering_without_connecting_other (test_stick_integration.MenuIntegrationTests.test_context_target_survives_network_reordering_without_connecting_other)` | G6 |
| 51 | FAIL | `test_disappeared_context_target_does_not_fall_through_to_another_network (test_stick_integration.MenuIntegrationTests.test_disappeared_context_target_does_not_fall_through_to_another_network)` | G6 |
| 52 | FAIL | `test_dpad_focus_moves_pointer_and_primary_click_follows_it (test_stick_integration.MenuIntegrationTests.test_dpad_focus_moves_pointer_and_primary_click_follows_it)` | G6 |
| 53 | FAIL | `test_dpad_network_focus_follows_reordered_rows_before_primary_click (test_stick_integration.MenuIntegrationTests.test_dpad_network_focus_follows_reordered_rows_before_primary_click)` | G6 |
| 54 | FAIL | `test_expanded_context_rejects_connect_after_status_changes_to_active (test_stick_integration.MenuIntegrationTests.test_expanded_context_rejects_connect_after_status_changes_to_active)` | G6 |
| 55 | FAIL | `test_freely_moved_pointer_stays_physical_when_network_rows_reorder (test_stick_integration.MenuIntegrationTests.test_freely_moved_pointer_stays_physical_when_network_rows_reorder)` | G6 |
| 56 | FAIL | `test_keyboard_keeps_pointer_inactive_and_text_shortcuts_keep_their_meaning (test_stick_integration.MenuIntegrationTests.test_keyboard_keeps_pointer_inactive_and_text_shortcuts_keep_their_meaning)` | G6 |
| 57 | FAIL | `test_power_target_still_requires_a_separate_confirmation (test_stick_integration.MenuIntegrationTests.test_power_target_still_requires_a_separate_confirmation)` | G6 |
| 58 | FAIL | `test_provider_refresh_invalidates_popup_when_connect_changes_to_disconnect (test_stick_integration.MenuIntegrationTests.test_provider_refresh_invalidates_popup_when_connect_changes_to_disconnect)` | G6 |
| 59 | FAIL | `test_rejected_stale_popup_confirmation_still_requests_redraw (test_stick_integration.MenuIntegrationTests.test_rejected_stale_popup_confirmation_still_requests_redraw)` | G6 |
| 60 | FAIL | `test_secondary_buttons_open_context_and_dpad_selects_immediately (test_stick_integration.MenuIntegrationTests.test_secondary_buttons_open_context_and_dpad_selects_immediately) (button=308)` | G6 |
| 61 | FAIL | `test_secondary_buttons_open_context_and_dpad_selects_immediately (test_stick_integration.MenuIntegrationTests.test_secondary_buttons_open_context_and_dpad_selects_immediately) (button=318)` | G6 |
| 62 | FAIL | `test_r3_is_reserved_and_does_not_toggle_tray (test_v3_ui.HomeStateTests.test_r3_is_reserved_and_does_not_toggle_tray)` | G5 |
| 63 | FAIL | `test_tray_and_wheel_motion_are_time_based (test_v3_ui.HomeStateTests.test_tray_and_wheel_motion_are_time_based)` | G5 |
| 64 | FAIL | `test_file_details_first_animation_frame_is_drawable (test_v3_ui.V3RenderTests.test_file_details_first_animation_frame_is_drawable)` | G5 |
| 65 | FAIL | `test_home_and_settings_are_interactive (test_v3_ui.V3RenderTests.test_home_and_settings_are_interactive)` | G5 |
| 66 | FAIL | `test_shortcut_tray_tiles_touch_from_fixed_a_position (test_v3_ui.V3RenderTests.test_shortcut_tray_tiles_touch_from_fixed_a_position)` | G5 |
| 67 | FAIL | `test_shell_exception_never_reports_or_prints_secret_payload (test_wifi_panel.PanelTests.test_shell_exception_never_reports_or_prints_secret_payload)` | G2 |
