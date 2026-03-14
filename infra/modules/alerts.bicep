// filepath: infra/modules/alerts.bicep
// ============================================================
// Azure Monitor Alerts + Budget Alerts (T807 / T807a)
//
// Alert categories:
//   1. Infrastructure — CPU, memory, restarts on Container Apps
//   2. Application — HTTP 5xx spike, latency p95 budget
//   3. Database — CPU %, storage %, connection count
//   4. Budget — monthly cost threshold with email notification
//
// Action group delivers notifications via email + (optional) webhook.
// All alerts use the same action group for centralised routing.
// ============================================================

param projectName string
param environment string
param location string
param tags object

@description('Resource ID of the Application Insights instance')
param appInsightsResourceId string

@description('Resource ID of the Container Apps Environment')
param containerAppsEnvironmentId string

@description('Resource ID of the PostgreSQL Flexible Server')
param postgresqlResourceId string

@description('Email address for alert notifications')
param alertEmail string = 'ops@investorinsights.dev'

@description('Optional webhook URL for PagerDuty / Slack / Teams')
param webhookUrl string = ''

@description('Monthly budget limit in USD')
param monthlyBudgetUsd int = environment == 'dev' ? 50 : 500

@description('Budget alert thresholds (% of budget)')
param budgetThresholdPercents array = [50, 80, 100]

// ── Naming ──────────────────────────────────────────────────────
var prefix = '${projectName}-${environment}'

// ── Action Group ────────────────────────────────────────────────
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-${prefix}'
  location: 'Global'
  tags: tags
  properties: {
    groupShortName: 'InvInsights'
    enabled: true
    emailReceivers: [
      {
        name: 'OpsTeam'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
    webhookReceivers: empty(webhookUrl) ? [] : [
      {
        name: 'Webhook'
        serviceUri: webhookUrl
        useCommonAlertSchema: true
      }
    ]
  }
}

// =====================================================================
// 1. Application Alerts (App Insights — Kusto-based)
// =====================================================================

// ── HTTP 5xx Spike ──────────────────────────────────────────────
resource alert5xx 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-${prefix}-http-5xx-spike'
  location: location
  tags: tags
  properties: {
    displayName: '${prefix} — HTTP 5xx Spike'
    description: 'Fires when > 10 server errors in a 5-minute window.'
    severity: 2 // Warning
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [appInsightsResourceId]
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where resultCode startswith "5"
            | summarize ErrorCount = count() by bin(timestamp, 5m)
          '''
          timeAggregation: 'Total'
          metricMeasureColumn: 'ErrorCount'
          operator: 'GreaterThan'
          threshold: 10
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ── API Latency p95 > Budget ────────────────────────────────────
resource alertLatency 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-${prefix}-api-latency-p95'
  location: location
  tags: tags
  properties: {
    displayName: '${prefix} — API Latency p95 > 2s'
    description: 'Fires when p95 API response time exceeds 2000 ms over 10 minutes.'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT10M'
    scopes: [appInsightsResourceId]
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where url !has "/health"
            | summarize p95_ms = percentile(duration, 95) by bin(timestamp, 10m)
          '''
          timeAggregation: 'Maximum'
          metricMeasureColumn: 'p95_ms'
          operator: 'GreaterThan'
          threshold: 2000
          failingPeriods: {
            numberOfEvaluationPeriods: 2
            minFailingPeriodsToAlert: 2
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ── Chat TTFT > Budget ──────────────────────────────────────────
resource alertChatTTFT 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-${prefix}-chat-ttft'
  location: location
  tags: tags
  properties: {
    displayName: '${prefix} — Chat TTFT > 5s'
    description: 'Fires when chat streaming first-token latency exceeds 5000 ms.'
    severity: 3
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [appInsightsResourceId]
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where url has "/chat"
            | summarize p95_ms = percentile(duration, 95) by bin(timestamp, 15m)
          '''
          timeAggregation: 'Maximum'
          metricMeasureColumn: 'p95_ms'
          operator: 'GreaterThan'
          threshold: 5000
          failingPeriods: {
            numberOfEvaluationPeriods: 2
            minFailingPeriodsToAlert: 2
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// =====================================================================
// 2. Infrastructure Alerts (Container Apps — metric-based)
// =====================================================================

// ── API Container Restart ───────────────────────────────────────
resource alertRestarts 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${prefix}-container-restarts'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Fires when container restarts exceed 3 in 15 minutes.'
    severity: 1 // Error
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [containerAppsEnvironmentId]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.MultipleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'RestartCount'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'microsoft.app/managedenvironments'
          metricName: 'RestartCount'
          operator: 'GreaterThan'
          threshold: 3
          timeAggregation: 'Total'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// =====================================================================
// 3. Database Alerts (PostgreSQL Flexible Server — metric-based)
// =====================================================================

// ── DB CPU > 80% ────────────────────────────────────────────────
resource alertDbCpu 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${prefix}-db-cpu-high'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Fires when PostgreSQL CPU exceeds 80% for 10 minutes.'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT10M'
    scopes: [postgresqlResourceId]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.MultipleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'CpuPercent'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'Microsoft.DBforPostgreSQL/flexibleServers'
          metricName: 'cpu_percent'
          operator: 'GreaterThan'
          threshold: 80
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// ── DB Storage > 85% ────────────────────────────────────────────
resource alertDbStorage 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${prefix}-db-storage-high'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Fires when PostgreSQL storage utilisation exceeds 85%.'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
    scopes: [postgresqlResourceId]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.MultipleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'StoragePercent'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'Microsoft.DBforPostgreSQL/flexibleServers'
          metricName: 'storage_percent'
          operator: 'GreaterThan'
          threshold: 85
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// ── DB Active Connections > 80% of limit ────────────────────────
resource alertDbConnections 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-${prefix}-db-connections-high'
  location: 'Global'
  tags: tags
  properties: {
    description: 'Fires when PostgreSQL active connections exceed 40 (80% of B1ms 50-conn limit).'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [postgresqlResourceId]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.MultipleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ActiveConnections'
          criterionType: 'StaticThresholdCriterion'
          metricNamespace: 'Microsoft.DBforPostgreSQL/flexibleServers'
          metricName: 'active_connections'
          operator: 'GreaterThan'
          threshold: environment == 'dev' ? 40 : 150
          timeAggregation: 'Maximum'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// =====================================================================
// 4. Budget Alert (Azure Consumption — T807a)
// =====================================================================

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'budget-${prefix}'
  properties: {
    category: 'Cost'
    amount: monthlyBudgetUsd
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '2026-03-01'
    }
    notifications: {
      alert50pct: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: budgetThresholdPercents[0]
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
      alert80pct: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: budgetThresholdPercents[1]
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
      alert100pct: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: budgetThresholdPercents[2]
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
      forecast100pct: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactEmails: [alertEmail]
        thresholdType: 'Forecasted'
      }
    }
  }
}

// ── Outputs ─────────────────────────────────────────────────────
output actionGroupId string = actionGroup.id
output actionGroupName string = actionGroup.name
output budgetName string = budget.name
