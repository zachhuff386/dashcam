#ifndef DASHCAM_STREAM_H
#define DASHCAM_STREAM_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <signal.h>
#include <unistd.h>
#include <glib.h>
#include <gst/gst.h>

// Globals
GMainLoop *main_loop;
GstElement *main_pipeline, *main_source, *main_queue;
GstElement *temp_pipeline, *temp_source, *temp_queue;
GstElement *first_bin, *first_queue, *first_parse,
  *first_muxer, *first_sink;
GstElement *second_bin, *second_queue, *second_parse,
  *second_muxer, *second_sink;
guint main_bus_watch_id, temp_bus_watch_id, stream_state;
guint active_bin = 1;
guint exiting = 0;

// Command line options
gchar *dev_name = NULL;
gchar *media_type = NULL;
gchar *muxer_name = NULL;
gchar *output_path = NULL;
gint dev_delay = 10000;
gchar *stream_state_path = "/var/run/dashcam_stream_state";
gint width = 0;
gint height = 0;
gint framerate = 0;
gint segment_length = 0;
gint segment_counter = 0;

static void exit_app();
static void create_main_pipeline();
static void create_temp_pipeline();
static void create_bin(guint);
static void set_stream_state(guint);
static void set_sink_location(GstElement *);
static void split_output(guint);
static gboolean split_output_cb(gpointer);
static gboolean main_bus_cb(GstBus *, GstMessage *, gpointer);
static gboolean temp_bus_cb(GstBus *, GstMessage *, gpointer);

#endif
