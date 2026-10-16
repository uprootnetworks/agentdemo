<?php
/**
 * Plugin Name: Agent Demo Diagnostic Intake
 * Description: A controlled diagnostic intake that validates reports and returns a receipt without storing their contents.
 * Version: 1.0.0
 */

if (!defined('ABSPATH')) {
    exit;
}

add_action('rest_api_init', function () {
    register_rest_route('agentdemo/v1', '/diagnostics', array(
        'methods' => 'POST',
        // Intentionally public, stateless demo intake. No account or privileged operation.
        'permission_callback' => '__return_true',
        'callback' => 'uproot_agentdemo_receive',
    ));
});

function uproot_agentdemo_receive(WP_REST_Request $request) {
    if (strlen($request->get_body()) > 32768) {
        return new WP_Error('too_large', 'Maximum report size is 32 KiB.', array('status' => 413));
    }
    $content_type = $request->get_header('content-type');
    if (strtolower(trim(explode(';', $content_type)[0])) !== 'application/json') {
        return new WP_Error('bad_type', 'Use application/json.', array('status' => 415));
    }
    // Limit repeat submissions; do not trust forwarded client IP headers.
    $ip = isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : 'unknown';
    $key = 'agentdemo_' . substr(hash_hmac('sha256', $ip, wp_salt('nonce')), 0, 32);
    $count = (int) get_transient($key);
    if ($count >= 10) {
        return new WP_Error('rate_limit', 'Try again in one minute.', array('status' => 429));
    }
    set_transient($key, $count + 1, MINUTE_IN_SECONDS);

    $data = json_decode($request->get_body(), true, 8);
    $keys = array('schema', 'collected_at', 'workstation', 'resolver_settings', 'target', 'dns', 'https');
    if (!is_array($data) || count($data) !== count($keys) || array_diff($keys, array_keys($data)) ||
        $data['schema'] !== 'network-triage-v1' || $data['target'] !== 'https://uprootnetworks.com/' ||
        !is_string($data['collected_at']) || strlen($data['collected_at']) > 64 ||
        !is_string($data['resolver_settings']) || strlen($data['resolver_settings']) > 16384 ||
        !is_array($data['workstation']) || !is_array($data['dns']) || !is_array($data['https'])) {
        return new WP_Error('bad_report', 'Expected a Network Triage diagnostic report.', array('status' => 400));
    }
    foreach (array('hostname', 'os', 'release') as $field) {
        if (!isset($data['workstation'][$field]) || !is_string($data['workstation'][$field]) ||
            strlen($data['workstation'][$field]) > 255) {
            return new WP_Error('bad_workstation', 'Invalid workstation fields.', array('status' => 400));
        }
    }
    if (count($data['workstation']) !== 3 || !isset($data['dns']['status'], $data['https']['status']) ||
        !in_array($data['dns']['status'], array('resolved', 'error'), true) ||
        !in_array($data['https']['status'], array('verified', 'error'), true)) {
        return new WP_Error('bad_result', 'Invalid diagnostic result.', array('status' => 400));
    }
    // Do not store, email, or log the report. Return no submitted content.
    $response = new WP_REST_Response(array(
        'accepted' => true,
        'receipt' => wp_generate_uuid4(),
        'received_bytes' => strlen($request->get_body()),
        'report_stored_by_plugin' => false,
    ), 200);
    $response->header('Cache-Control', 'no-store');
    return $response;
}
