{{/*
Expand the name of the chart.
*/}}
{{- define "inferav22.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "inferav22.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s" $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "inferav22.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
app.kubernetes.io/name: {{ include "inferav22.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "inferav22.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inferav22.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Node selector for the specified cloud
*/}}
{{- define "inferav22.nodeSelector" -}}
{{- $cloud := .Values.cloud -}}
{{- $selector := index .Values.nodeSelectors $cloud -}}
{{- if $selector }}
{{- toYaml $selector }}
{{- else }}
kubernetes.io/arch: arm64
{{- end }}
{{- end }}
